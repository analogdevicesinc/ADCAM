/*
 * BSD 3-Clause License
 *
 * Copyright (c) 2019, Analog Devices, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
#include "server.h"
#include "aditof/aditof.h"
#include "aditof/sensor_enumerator_factory.h"
#include "aditof/sensor_enumerator_interface.h"
#include "buffer.pb.h"

#include "../../sdk/src/connections/target/v4l_buffer_access_interface.h"

#ifdef USE_GLOG
#include <glog/logging.h>
#else
#include <aditof/log.h>
#endif
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <future>
#include <iostream>
#include <linux/videodev2.h>
#include <map>
#include <queue>
#include <string>
#include <sys/time.h>
#include <thread>
#ifdef WITH_NETWORK_COMPRESSION
#ifdef WITH_NETWORK_COMPRESSION_LZ4
    #include <lz4.h>
    // High-compression API (optional)
    #include <lz4hc.h>
#else
    #include <RVL.h>
#endif //WITH_NETWORK_COMPRESSION_LZ4
#endif

using namespace google::protobuf::io;

static const int FRAME_PREPADDING_BYTES = 2;
static int interrupted = 0;

/* Available sensors */
std::vector<std::shared_ptr<aditof::DepthSensorInterface>> depthSensors;
bool sensors_are_created = false;
bool clientEngagedWithSensors = false;
bool isConnectionClosed = true;
bool gotStream_off = true;

std::unique_ptr<aditof::SensorEnumeratorInterface> sensorsEnumerator;

/* Server only works with one depth sensor */
std::shared_ptr<aditof::DepthSensorInterface> camDepthSensor;
std::shared_ptr<aditof::V4lBufferAccessInterface> sensorV4lBufAccess;
std::atomic<uint32_t> processedFrameSize{0};

static payload::ClientRequest buff_recv;
static payload::ServerResponse buff_send;

//sending frames separately without serializing it
std::shared_ptr<uint16_t[]> buff_frame_to_be_captured = nullptr;
std::shared_ptr<uint16_t[]> buff_frame_to_send = nullptr;
std::atomic<uint32_t> buff_frame_length{0};
bool m_frame_ready = false;

static std::map<std::string, api_Values> s_map_api_Values;
static void Initialize();
static void data_transaction();
void invoke_sdk_api(payload::ClientRequest buff_recv);
static bool Client_Connected = false;
static bool no_of_client_connected = false;
bool latest_sent_msg_is_was_buffered = false;
static std::queue<aditof::Adsd3500Status> adsd3500InterruptsQueue;
static std::timed_mutex adsd3500InterruptsQueueMutex;

// A test mode that server can be set to. After sending one frame from sensor to host, it will repeat
// sending the same frame over and over without acquiring any other frame from sensor. This allows
// testing the network link speed because it eliminates operations on target such as getting the frame
// from v4l2 interface, passing the frame through depth compute and any deep copying.
static bool sameFrameEndlessRepeat = false;

// Variables for synchronizing the main thread and the thread responsible for capturing frames from hardware
std::mutex
    frameMutex; // used for making sure operations on queue are not done simultaneously by the 2 threads
std::condition_variable
    cvGetFrame; // used for threads to signal when to start capturing a frame or when a frame has become available
bool goCaptureFrame =
    false; // Flag used by main thread to tell the frame capturing thread to start capturing a frame
bool frameCaptured =
    false; // Flag used by frame capturing thread to tell the main thread that a frame has become available
std::thread
    frameCaptureThread; // The thread instance for the capturing frame thread
bool keepCaptureThreadAlive =
    false; // Flag used by frame capturing thread to know whether to continue or finish
std::atomic<bool> bufferReallocationInProgress(false); // Flag to pause operations during buffer reallocation

std::unique_ptr<zmq::socket_t> server_socket;
uint32_t max_send_frames = 10;
std::atomic<bool> running(false);
std::atomic<bool> stop_flag(false);
std::thread data_transaction_thread;
std::timed_mutex connection_mtx;
std::mutex mtx;
std::condition_variable cv;
std::thread stream_thread;
static std::unique_ptr<zmq::context_t> context;
static std::unique_ptr<zmq::socket_t> server_cmd;
static std::unique_ptr<zmq::socket_t> monitor_socket;
const auto get_frame_timeout =
    std::chrono::milliseconds(1000); // time to wait for a frame to be captured
std::unique_ptr<uint8_t[]> buff_frame_compressed = nullptr;

#ifdef WITH_NETWORK_COMPRESSION

// 0 = fast default compression, >0 = use LZ4 HC with level (1..LZ4HC_CLEVEL_MAX) //  LZ4HC_CLEVEL_MAX = 12
std::atomic<int> compression_level{0};

#include <deque>
#include <mutex>
#include <cstddef>
#include <type_traits>
#include <stdexcept>
#include <limits>

/*
 RunningAverage<T>

 - Maintains a running average over the last N items (sliding window).
 - Thread-safe: all public methods lock an internal mutex.
 - O(1) amortized add, O(1) average, O(1) min, O(1) max.
 - Provides reset(), count(), capacity(), min(), max(), and average().
 - Template T must be a numeric type (integral or floating).
*/

template<typename T>
class RunningAverage {
    static_assert(std::is_arithmetic<T>::value, "RunningAverage requires a numeric type");

public:
    explicit RunningAverage(std::size_t capacity)
        : m_capacity(capacity),
          m_nextIndex(0),
          m_sum(0.0L)
    {
        if (capacity == 0) {
            throw std::invalid_argument("capacity must be > 0");
        }
    }

    // Add a new value to the sliding window
    void add(const T& value) {
        std::lock_guard<std::mutex> lock(m_mutex);

        const std::size_t idx = m_nextIndex++;
        m_values.emplace_back(idx, value);
        m_sum += static_cast<long double>(value);

        // Maintain monotonic increasing deque for min
        while (!m_minDeque.empty() && m_minDeque.back().second > value) {
            m_minDeque.pop_back();
        }
        m_minDeque.emplace_back(idx, value);

        // Maintain monotonic decreasing deque for max
        while (!m_maxDeque.empty() && m_maxDeque.back().second < value) {
            m_maxDeque.pop_back();
        }
        m_maxDeque.emplace_back(idx, value);

        // If over capacity, evict oldest
        if (m_values.size() > m_capacity) {
            auto oldest = m_values.front();
            m_values.pop_front();
            m_sum -= static_cast<long double>(oldest.second);

            if (!m_minDeque.empty() && m_minDeque.front().first == oldest.first) {
                m_minDeque.pop_front();
            }
            if (!m_maxDeque.empty() && m_maxDeque.front().first == oldest.first) {
                m_maxDeque.pop_front();
            }
        }
    }

    // Return current average; throws if no values
    long double average() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_values.empty()) {
            throw std::runtime_error("average(): no values in window");
        }
        return m_sum / static_cast<long double>(m_values.size());
    }

    // Return current minimum; throws if no values
    T min() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_values.empty()) {
            throw std::runtime_error("min(): no values in window");
        }
        return m_minDeque.front().second;
    }

    // Return current maximum; throws if no values
    T max() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_values.empty()) {
            throw std::runtime_error("max(): no values in window");
        }
        return m_maxDeque.front().second;
    }

    // Number of items currently in the window
    std::size_t count() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_values.size();
    }

    // The configured window capacity (N)
    std::size_t capacity() const noexcept {
        return m_capacity;
    }

    // Clear the window and reset statistics
    void reset() {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_values.clear();
        m_minDeque.clear();
        m_maxDeque.clear();
        m_sum = 0.0L;
        m_nextIndex = 0;
    }

private:
    // store pairs of (index, value) so monotonic deques can compare indices on eviction
    std::deque<std::pair<std::size_t, T>> m_values;
    std::deque<std::pair<std::size_t, T>> m_minDeque;
    std::deque<std::pair<std::size_t, T>> m_maxDeque;

    const std::size_t m_capacity;
    std::size_t m_nextIndex;
    long double m_sum;

    mutable std::mutex m_mutex;
};

// Compression statistics (declared after RunningAverage class definition)
static RunningAverage<double> compressionTime(50);
static RunningAverage<double> compressionPercentage(50);
#endif // WITH_NETWORK_COMPRESSION

struct clientData {
    bool hasFragments;
    std::vector<char> data;
};

static void close_zmq_connection() {

    buff_frame_compressed.reset();

    // Stop the sensor if not already stopped
    if (!gotStream_off && camDepthSensor) {
        aditof::Status status = camDepthSensor->stop();
        gotStream_off = (status == aditof::Status::OK);
    }

    if (server_socket) {
        server_socket->close();
        server_socket.reset();
    }

    LOG(INFO) << "ZMQ Client Connection closed.";
    isConnectionClosed = true;
}

void stream_zmq_frame() {

    // Establish the connection and stream the frames. Since zmq is not thread safe
    // It needs to be initialized and used in same thread.

    static zmq::context_t zmq_context(1);
    server_socket =
        std::make_unique<zmq::socket_t>(zmq_context, zmq::socket_type::push);
    server_socket->setsockopt(ZMQ_SNDHWM, (int *)&max_send_frames,
                              sizeof(max_send_frames));
    server_socket->setsockopt(ZMQ_SNDTIMEO, FRAME_TIMEOUT);
    server_socket->bind("tcp://*:5555");
    LOG(INFO) << "ZMQ server socket connection established.";

    LOG(INFO) << "stream_frame thread running in the background.";

    running = true;

#ifdef WITH_NETWORK_COMPRESSION
    buff_frame_compressed.reset();
#endif //WITH_NETWORK_COMPRESSION

    while (true) {

        if (stop_flag.load()) {
            LOG(INFO) << "stream_frame thread is exiting.";
            break;
        }

        // 1. Wait for frame to be captured on the other thread
        std::unique_lock<std::mutex> lock(frameMutex);
        if (!cvGetFrame.wait_for(lock, std::chrono::milliseconds(500), []() {
                return frameCaptured || stop_flag.load();
            })) {
            LOG(WARNING) << "stream_zmq_frame: Timeout waiting for "
                            "frameCaptured or stop_flag";
            continue;
        }
        
        // Skip if buffer reallocation is in progress
        if (bufferReallocationInProgress.load()) {
            frameCaptured = false;
            lock.unlock();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        // 2. Copy the captured frame to send buffer
        // Create local copies to keep buffers alive during operations
        // Capture size and pointers together atomically
        auto local_send_buffer = buff_frame_to_send;
        auto local_capture_buffer = buff_frame_to_be_captured;
        uint32_t local_frame_length_shorts = processedFrameSize.load();
        uint32_t local_frame_length_bytes = local_frame_length_shorts * sizeof(uint16_t);
        
        if (local_send_buffer && local_capture_buffer) {
            memcpy(local_send_buffer.get(), local_capture_buffer.get(), local_frame_length_bytes);
        }
        frameCaptured = false;

        // 3. Trigger the other thread to capture another frame while we do stuff with current frame
        goCaptureFrame = true;
        lock.unlock();
        cvGetFrame.notify_one();

        if (!server_socket) {
            LOG(ERROR) << "ZMQ server socket is not initialized!";
            break;
        }

        void *buf_to_send = nullptr;

#ifdef WITH_NETWORK_COMPRESSION

        auto start = std::chrono::high_resolution_clock::now();
        uint32_t bfl = 1;

#ifdef WITH_NETWORK_COMPRESSION_LZ4
        // Do LZ4 compression here
        {
            uint32_t *compressedSize = nullptr;
            uint32_t maxCompressedSize = LZ4_compressBound(local_frame_length_bytes);
            if (buff_frame_compressed == nullptr) {
                LOG(INFO) << "Allocating compression buffer of size (LZ4): " << 3 + sizeof(*compressedSize) + maxCompressedSize << " bytes";
                buff_frame_compressed.reset(new uint8_t[3 + sizeof(*compressedSize) + maxCompressedSize]);
            }
            if (buff_frame_compressed) {
                buff_frame_compressed[0] = 'L';
                buff_frame_compressed[1] = 'Z';
                buff_frame_compressed[2] = '4';
                compressedSize = (uint32_t *)(buff_frame_compressed.get() + 3);

                if (compression_level.load() > 0) {
                    int level = compression_level.load();
                    if (level > LZ4HC_CLEVEL_MAX) level = LZ4HC_CLEVEL_MAX;
                    *compressedSize = LZ4_compress_HC(
                        (const char *)local_send_buffer.get(), (char *)(buff_frame_compressed.get() + sizeof(*compressedSize) + 3),
                        local_frame_length_bytes, maxCompressedSize, level);
                } else {
                    *compressedSize = LZ4_compress_default(
                        (const char *)local_send_buffer.get(), (char *)(buff_frame_compressed.get() + sizeof(*compressedSize) + 3),
                        local_frame_length_bytes, maxCompressedSize);
                }

                if (*compressedSize > 0) {
                    bfl = local_frame_length_bytes;
                    local_frame_length_bytes = 3 + sizeof(*compressedSize) + *compressedSize;

                    buf_to_send = (void *)buff_frame_compressed.get();
                } else {
                    LOG(ERROR) << "LZ4 compression failed!";
                    continue;
                }
            }
        }
#else 
        // Do RVL and JPEG-Turbo compression here
        {
            // Compress depth data with RVL
            uint32_t *compressedSize = nullptr;
            uint32_t maxCompressedSize = local_frame_length_bytes;
            if (buff_frame_compressed == nullptr) {
                LOG(INFO) << "Allocating compression buffer of size (RVL): " << 3 + sizeof(*compressedSize) + maxCompressedSize << " bytes";
                buff_frame_compressed.reset(new uint8_t[3 + sizeof(*compressedSize) + maxCompressedSize]);
            }
            if (buff_frame_compressed) {
                buff_frame_compressed[0] = 'R';
                buff_frame_compressed[1] = 'V';
                buff_frame_compressed[2] = 'L';
                compressedSize = (uint32_t *)(buff_frame_compressed.get() + 3);

                *compressedSize = RVL::CompressRVL(
                    (short *)local_send_buffer.get(), (char *)(buff_frame_compressed.get() + sizeof(*compressedSize) + 3),
                    local_frame_length_shorts);

                if (*compressedSize > 0) {
                    bfl = local_frame_length_bytes;
                    local_frame_length_bytes = 3 + sizeof(*compressedSize) + *compressedSize;

                    buf_to_send = (void *)buff_frame_compressed.get();
                } else {
                    LOG(ERROR) << "LZ4 compression failed!";
                    continue;
                }
            }
        }
#endif // WITH_NETWORK_COMPRESSION_LZ4

        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
        
        compressionTime.add(duration);
        compressionPercentage.add(100.0 * ((double)local_frame_length_bytes / bfl));

        LOG(WARNING) << compressionTime.average() << " ms (avg), "
                    << compressionTime.min() << " ms (min), "
                    << compressionTime.max() << " ms (max), "
                    << compressionPercentage.average() << " % (avg)";

#else
        buf_to_send = (void *)local_send_buffer.get();
#endif // WITH_NETWORK_COMPRESSION

        zmq::message_t message(local_frame_length_bytes);
        memcpy(message.data(), buf_to_send, local_frame_length_bytes);
        auto send = server_socket->send(message, zmq::send_flags::none);
        if (!send.has_value()) {
            LOG(INFO) << "Client is busy , dropping the frame!";
        }
    }

    {
        std::lock_guard<std::mutex> thread_lock(mtx);
        running = false;
    }

    cv.notify_all();

#ifdef WITH_NETWORK_COMPRESSION
        buff_frame_compressed.reset();
#endif //WITH_NETWORK_COMPRESSION

    LOG(INFO) << "stream_zmq_frame thread stopped successfully.";
}

void start_stream_thread() {

    // Reset the stop flag
    stop_flag.store(false);

    keepCaptureThreadAlive = true;

    if (stream_thread.joinable()) {
        stream_thread.join(); // Ensure the previous thread is cleaned up
    }

    stream_thread = std::thread(stream_zmq_frame); // Assign thread
}

void stop_stream_thread() {
    if (!running) {
        return; // If thread is already stopped exit the function.
    }

    {
        std::lock_guard<std::mutex> lock(mtx);
        stop_flag.store(true);
    }
    cvGetFrame.notify_all();

    {
        std::unique_lock<std::mutex> lock(mtx);
        while (!cv.wait_for(lock, std::chrono::milliseconds(500),
                            [] { return running.load() == false; })) {
            // Wait until the thread has stopped
            LOG(INFO) << "Waiting for stream thread to stop...";
        }
    }

    // Flush the messages
    if (server_socket) {
        server_socket->setsockopt(ZMQ_LINGER, 0);
    }

    if (stream_thread.joinable()) {
        stream_thread.join(); // Ensure the thread exits cleanly.
    }

    LOG(INFO) << "stream thread stopped.";
}

aditof::SensorInterruptCallback callback = [](aditof::Adsd3500Status status) {
    {
        if (adsd3500InterruptsQueueMutex.try_lock_for(
                std::chrono::milliseconds(500))) {
            adsd3500InterruptsQueue.push(status);
            adsd3500InterruptsQueueMutex.unlock();
        } else {
            LOG(ERROR)
                << "Unable to lock adsd3500InterruptsQueueMutex for 500 ms";
        }
    }
    DLOG(INFO) << "ADSD3500 interrupt occured: status = " << status;
};

// Function executed in the capturing frame thread
static void captureFrameFromHardware() {
    while (keepCaptureThreadAlive) {

        if (stop_flag.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        // 1. Wait for the signal to start capturing a new frame
        std::unique_lock<std::mutex> lock(frameMutex);
        if (!cvGetFrame.wait_for(lock, std::chrono::milliseconds(500), [] {
                return goCaptureFrame || !keepCaptureThreadAlive;
            })) {
            // If the wait times out, check if we should keep the thread alive
            continue;
        }

        if (!keepCaptureThreadAlive) {
            break;
        }

        // 2. The signal has been received, now go capture the frame
        goCaptureFrame = false;
        
        // Skip if buffer reallocation is in progress
        if (bufferReallocationInProgress.load()) {
            lock.unlock();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        // Send frames to PC via ZMQ socket.
        if (!buff_frame_to_be_captured) {
            LOG(ERROR)
                << "buff_frame_to_be_captured is nullptr, cannot capture frame.";
            continue;
        }
        
        // Create a local shared_ptr copy to keep the buffer alive during getFrame
        auto local_capture_buffer = buff_frame_to_be_captured;
        
        // Unlock before the potentially long getFrame operation
        lock.unlock();
        
        // Call getFrame directly - no async needed
        // The local shared_ptr keeps the buffer alive even if the global one is reassigned
        aditof::Status status = camDepthSensor->getFrame(local_capture_buffer.get());
        
        if (status != aditof::Status::OK) {
            LOG(ERROR) << "Failed to get frame from sensor: " << status;
            continue;
        }

        if (stop_flag.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        
        // Re-acquire lock before setting frameCaptured flag
        lock.lock();

        // 3. Notify others that there is a new frame available
        frameCaptured = true;
        lock.unlock();
        cvGetFrame.notify_one();
    }
    LOG(INFO) << "Exiting captureFrameFromHardware thread.";
    return;
}

static void cleanup_sensors() {
    // Stop the frame capturing thread
    if (frameCaptureThread.joinable()) {
        keepCaptureThreadAlive = false;
        { std::lock_guard<std::mutex> lock(frameMutex); }
        cvGetFrame.notify_one();
        frameCaptureThread.join();
    }

    camDepthSensor->adsd3500_unregister_interrupt_callback(callback);
    sensorV4lBufAccess.reset();
    camDepthSensor.reset();

    {
        if (adsd3500InterruptsQueueMutex.try_lock_for(
                std::chrono::milliseconds(500))) {
            while (!adsd3500InterruptsQueue.empty()) {
                adsd3500InterruptsQueue.pop();
            }
            adsd3500InterruptsQueueMutex.unlock();
        } else {
            LOG(ERROR)
                << "Unable to lock adsd3500InterruptsQueueMutex in 500 ms";
        }
    }

    sensors_are_created = false;
    clientEngagedWithSensors = false;
}

void server_event(std::unique_ptr<zmq::socket_t> &monitor) {
    while (!interrupted) {
        zmq::pollitem_t items[] = {
            {static_cast<void *>(monitor->handle()), 0, ZMQ_POLLIN, 0}};

        int rc;
        do {
            rc = zmq_poll(items, 1, 1000);
        } while (rc == -1 && zmq_errno() == EINTR);

        if (items[0].revents & ZMQ_POLLIN) {
            zmq_event_t event;
            zmq::message_t msg;
            monitor->recv(msg);
            memcpy(&event, msg.data(), sizeof(event));
            Network::callback_function(event);
        }
    }
}

int Network::callback_function(const zmq_event_t &event) {
    switch (event.event) {
    case ZMQ_EVENT_CONNECTED: {

        break;
    }
    case ZMQ_EVENT_CLOSED:
        std::cout << "Closed connection " << std::endl;
        if (Client_Connected && !no_of_client_connected) {
            std::cout << "Connection Closed" << std::endl;
            stop_stream_thread();
            if (isConnectionClosed == false) {
                close_zmq_connection();
            }
            if (clientEngagedWithSensors) {
                cleanup_sensors();
                clientEngagedWithSensors = false;
            }
            Client_Connected = false;
        } else {
            std::cout << "Another Client Connection Closed" << std::endl;
            no_of_client_connected = false;
        }
        break;
    case ZMQ_EVENT_CONNECT_RETRIED:
        std::cout << "Connection retried to " << std::endl;
        break;
    case ZMQ_EVENT_ACCEPTED:
        buff_send.Clear();
        if (!Client_Connected) {
            std::cout << "Conn Established" << std::endl;
            {
                if (connection_mtx.try_lock_for(
                        std::chrono::milliseconds(200))) {
                    Client_Connected = true;
                    connection_mtx.unlock();
                } else {
                    LOG(ERROR) << "Unable to lock the connection_mtx";
                    break; // Not able to lock the mutex in 100 ms
                }
            }
            buff_send.set_message("Connection Allowed");
        } else {
            std::cout << "Another client connected" << std::endl;
            no_of_client_connected = true;
        }
        break;
    case ZMQ_EVENT_DISCONNECTED: {
        if (Client_Connected && !no_of_client_connected) {
            std::cout << "Connection Closed" << std::endl;
            stop_stream_thread();
            if (isConnectionClosed == false) {
                close_zmq_connection();
            }
            if (clientEngagedWithSensors) {
                cleanup_sensors();
                clientEngagedWithSensors = false;
            }
            Client_Connected = false;
        } else {
            std::cout << "Another Client Connection Closed" << std::endl;
            no_of_client_connected = false;
        }
        break;
    }
    default:
#ifdef NW_DEBUG
        std::cout << "Event: " << event.event << " on " << addr << std::endl;
#endif
        break;
    }
    return 0;
}

void data_transaction() {

    while (!interrupted) {

        zmq::message_t request;

        if (connection_mtx.try_lock_for(std::chrono::milliseconds(200))) {

            if (Client_Connected) {
                if (server_cmd->recv(request, zmq::recv_flags::dontwait)) {
                    google::protobuf::io::ArrayInputStream ais(request.data(),
                                                               request.size());
                    google::protobuf::io::CodedInputStream coded_input(&ais);
                    buff_recv.ParseFromCodedStream(&coded_input);
                    invoke_sdk_api(buff_recv);

                    // Preparing to send the data
                    unsigned int siz = buff_send.ByteSize();
                    unsigned char *pkt = new unsigned char[siz];

                    google::protobuf::io::ArrayOutputStream aos(pkt, siz);
                    google::protobuf::io::CodedOutputStream coded_output(&aos);
                    buff_send.SerializeToCodedStream(&coded_output);

                    // Create a zmq message
                    zmq::message_t reply(pkt, siz);
                    if (server_cmd->send(reply, zmq::send_flags::none)) {
#ifdef NW_DEBUG
                        LOG(INFO) << "Data is sent ";
#endif
                    }
                    delete[] pkt;
                }
            }
            connection_mtx.unlock();
        } else {
            continue; // not able to lock connection mutex in 200 ms try again
        }
    }
}

void sigint_handler(int) { interrupted = 1; }

int main(int argc, char *argv[]) {
    signal(SIGINT, sigint_handler);
    signal(SIGTERM, sigint_handler);

    LOG(INFO) << "Server built \n"
              << "with SDK version: " << aditof::getApiVersion()
              << " | branch: " << aditof::getBranchVersion()
              << " | commit: " << aditof::getCommitVersion();

    context = std::make_unique<zmq::context_t>(2);
    server_cmd = std::make_unique<zmq::socket_t>(*context, ZMQ_REP);

    // Set heartbeat options before binding
    int heartbeat_ivl = 1000;     // Send heartbeat every 1000 ms
    int heartbeat_timeout = 3000; // Timeout if no heartbeat received in 3000 ms
    int heartbeat_ttl = 5000;     // Heartbeat message TTL

    server_cmd->set(zmq::sockopt::heartbeat_ivl, heartbeat_ivl);
    server_cmd->set(zmq::sockopt::heartbeat_timeout, heartbeat_timeout);
    server_cmd->set(zmq::sockopt::heartbeat_ttl, heartbeat_ttl);

    // Bind the socket
    try {
        server_cmd->bind("tcp://*:5556");
    } catch (const zmq::error_t &e) {
        LOG(ERROR) << "Failed to bind Server socket : " << e.what();
        return 0;
    }

    std::string monitor_endpoint = "inproc://monitor";
    zmq_socket_monitor(server_cmd->handle(), "inproc://monitor", ZMQ_EVENT_ALL);

    monitor_socket = std::make_unique<zmq::socket_t>(*context, ZMQ_PAIR);
    // Connect the monitor socket
    monitor_socket->connect("inproc://monitor");

    // run thread to receive data
    data_transaction_thread = std::thread(data_transaction);
    data_transaction_thread.detach();

    Initialize();

    if (sensors_are_created) {
        cleanup_sensors();
    }

    while (!interrupted) {
        server_event(monitor_socket);
    }

    // Cleanup
    if (sensors_are_created) {
        cleanup_sensors();
    }
    clientEngagedWithSensors = false;

    stop_stream_thread();

    close_zmq_connection();

    if (server_cmd) {
        server_cmd->close();
        server_cmd.reset();
    }
    if (monitor_socket) {
        monitor_socket->close();
        monitor_socket.reset();
    }
    if (context) {
        context->close();
        context.reset();
    }

    return 0;
}

void invoke_sdk_api(payload::ClientRequest buff_recv) {
    buff_send.Clear();
    buff_send.set_server_status(::payload::ServerStatus::REQUEST_ACCEPTED);

    DLOG(INFO) << buff_recv.func_name() << " function";

    auto it = s_map_api_Values.find(buff_recv.func_name());

    if (it != s_map_api_Values.end()) {

        switch (s_map_api_Values[buff_recv.func_name()]) {

        case FIND_SENSORS: {
            if (!sensors_are_created) {
                sensorsEnumerator = aditof::SensorEnumeratorFactory::
                    buildTargetSensorEnumerator();
                if (!sensorsEnumerator) {
                    std::string errMsg =
                        "Failed to create a target sensor enumerator";
                    LOG(WARNING) << errMsg;
                    buff_send.set_message(errMsg);
                    buff_send.set_status(static_cast<::payload::Status>(
                        aditof::Status::UNAVAILABLE));
                    break;
                }

                sensorsEnumerator->searchSensors();
                sensorsEnumerator->getDepthSensors(depthSensors);
                sensors_are_created = true;
            }

            /* Add information about available sensors */

            // Depth sensor
            if (depthSensors.size() < 1) {
                buff_send.set_message("No depth sensors are available");
                buff_send.set_status(::payload::Status::UNREACHABLE);
                break;
            }

            camDepthSensor = depthSensors.front();
            auto pbSensorsInfo = buff_send.mutable_sensors_info();
            sensorV4lBufAccess =
                std::dynamic_pointer_cast<aditof::V4lBufferAccessInterface>(
                    camDepthSensor);

            std::string name;
            camDepthSensor->getName(name);
            auto pbDepthSensorInfo = pbSensorsInfo->mutable_image_sensors();
            pbDepthSensorInfo->set_name(name);

            std::string kernelversion;
            std::string ubootversion;
            std::string sdversion;
            auto cardVersion = buff_send.mutable_card_image_version();

            sensorsEnumerator->getKernelVersion(kernelversion);
            cardVersion->set_kernelversion(kernelversion);
            sensorsEnumerator->getUbootVersion(ubootversion);
            cardVersion->set_ubootversion(ubootversion);
            sensorsEnumerator->getSdVersion(sdversion);
            cardVersion->set_sdversion(sdversion);

            // This server is now subscribing for interrupts of ADSD3500
            aditof::Status registerCbStatus =
                camDepthSensor->adsd3500_register_interrupt_callback(callback);
            if (registerCbStatus != aditof::Status::OK) {
                LOG(WARNING) << "Could not register callback";
                // TBD: not sure whether to send this error to client or not
            }

            buff_send.set_status(
                static_cast<::payload::Status>(aditof::Status::OK));
            break;
        }

        case OPEN: {
            aditof::Status status = camDepthSensor->open();
            buff_send.set_status(static_cast<::payload::Status>(status));
            clientEngagedWithSensors = true;

            // At this stage, start the capturing frames thread
            keepCaptureThreadAlive = true;
            frameCaptureThread = std::thread(captureFrameFromHardware);

            break;
        }

        case START: {
            if (gotStream_off == true) {
                gotStream_off =
                    false; // reset this flag to expect the stream-off after start.
            }
            aditof::Status status = camDepthSensor->start();

            // When in test mode, capture 2 frames. 1st might be corrupt after a ADSD3500 reset.
            // 2nd frame will be the one sent over and over again by server in test mode.
            if (sameFrameEndlessRepeat) {
                for (int i = 0; i < 2; ++i) {
                    status = camDepthSensor->getFrame(
                        (uint16_t *)(buff_frame_to_send.get()));
                    if (status != aditof::Status::OK) {
                        LOG(ERROR) << "Failed to get frame!";
                    }
                }
            } else { // When in normal mode, trigger the capture thread to fetch a frame
                {
                    std::lock_guard<std::mutex> lock(frameMutex);
                    goCaptureFrame = true;
                }
                cvGetFrame.notify_one();
            }

            if (isConnectionClosed == false) {
                close_zmq_connection();
            }
            isConnectionClosed = false;
            start_stream_thread(); // Start the stream_frame thread .

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case STOP: {
            if (gotStream_off ==
                false) { // this operation will prevent to unecessary calling of stream-off
                stop_stream_thread();
                aditof::Status status = camDepthSensor->stop();
                if (status != aditof::Status::OK) {
                    gotStream_off = false;
                } else {
                    gotStream_off = true;
                }
                buff_send.set_status(static_cast<::payload::Status>(status));

                close_zmq_connection();
            }

            break;
        }

        case GET_AVAILABLE_MODES: {
            std::vector<uint8_t> aditofModes;
            aditof::Status status =
                camDepthSensor->getAvailableModes(aditofModes);
            for (auto &modeName : aditofModes) {
                buff_send.add_int32_payload(modeName);
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case GET_MODE_DETAILS: {
            aditof::DepthSensorModeDetails frameDetails;
            uint8_t modeName = buff_recv.func_int32_param(0);
            aditof::Status status =
                camDepthSensor->getModeDetails(modeName, frameDetails);
            auto protoContent = buff_send.mutable_depth_sensor_mode_details();
            protoContent->set_mode_number(frameDetails.modeNumber);
            protoContent->set_pixel_format_index(frameDetails.pixelFormatIndex);
            protoContent->set_frame_width_in_bytes(
                frameDetails.frameWidthInBytes);
            protoContent->set_frame_height_in_bytes(
                frameDetails.frameHeightInBytes);
            protoContent->set_base_resolution_width(
                frameDetails.baseResolutionWidth);
            protoContent->set_base_resolution_height(
                frameDetails.baseResolutionHeight);
            protoContent->set_metadata_size(frameDetails.metadataSize);
            protoContent->set_is_pcm(frameDetails.isPCM);
            protoContent->set_number_of_phases(frameDetails.numberOfPhases);
            for (int i = 0; i < frameDetails.frameContent.size(); i++) {
                protoContent->add_frame_content(
                    frameDetails.frameContent.at(i));
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case SET_MODE_BY_INDEX: {

            uint8_t mode = buff_recv.func_int32_param(0);
            
            // Check if streaming is active - if so, mode change is not safe
            if (running.load()) {
                LOG(ERROR) << "Cannot change mode while streaming is active. Please stop streaming first.";
                buff_send.set_status(static_cast<::payload::Status>(aditof::Status::BUSY));
                buff_send.set_message("Cannot change mode while streaming. Stop first.");
                break;
            }

            aditof::Status status = camDepthSensor->setMode(mode);
            if (status == aditof::Status::OK) {
                aditof::DepthSensorModeDetails aditofModeDetail;
                status = camDepthSensor->getModeDetails(mode, aditofModeDetail);
                if (status != aditof::Status::OK) {
                    buff_send.set_status(
                        static_cast<::payload::Status>(status));
                    break;
                }

                int width_tmp = aditofModeDetail.baseResolutionWidth;
                int height_tmp = aditofModeDetail.baseResolutionHeight;

                int new_processed_frame_size;
                if (aditofModeDetail.isPCM) {
                    new_processed_frame_size = width_tmp * height_tmp *
                                         aditofModeDetail.numberOfPhases;

                } else {
#ifdef DUAL
                    if (mode == 1 || mode == 0) {
                        new_processed_frame_size = width_tmp * height_tmp * 2;
                    } else {
                        new_processed_frame_size = width_tmp * height_tmp * 4;
                    }
#else
                    new_processed_frame_size = width_tmp * height_tmp * 4;
#endif
                }

                // Signal threads to pause operations
                bufferReallocationInProgress.store(true);
                // Wait for threads to finish any in-flight operations
                // by waiting for reference counts to drop to 1 (only global reference)
                int wait_iterations = 0;
                while ((buff_frame_to_send.use_count() > 1 || buff_frame_to_be_captured.use_count() > 1) && wait_iterations < 100) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    wait_iterations++;
                }
                
                if (wait_iterations >= 100) {
                    LOG(ERROR) << "Timeout waiting for thread references to clear! Force proceeding...";
                }
                
                // Additional safety: acquire and release lock to ensure no thread is in critical section
                {
                    std::lock_guard<std::mutex> temp_lock(frameMutex);
                    frameCaptured = false;
                    goCaptureFrame = false;
                }
                
                LOG(INFO) << "All thread references cleared, proceeding with reallocation";
                
                // Lock frameMutex to ensure threads aren't using the buffers
                // Also reset the frame capture state to avoid race conditions
                {
                    std::lock_guard<std::mutex> lock(frameMutex);
                    
                    // Reset frame state flags
                    frameCaptured = false;
                    goCaptureFrame = false;
                    
                    // First, reset old buffers to nullptr to release references
                    buff_frame_to_send.reset();
                    buff_frame_to_be_captured.reset();
                    
                    // Create new buffers
                    buff_frame_to_send = std::shared_ptr<uint16_t[]>(new uint16_t[new_processed_frame_size], std::default_delete<uint16_t[]>());
                    
                    buff_frame_to_be_captured = std::shared_ptr<uint16_t[]>(new uint16_t[new_processed_frame_size], std::default_delete<uint16_t[]>());
                    
                    // Update size AFTER buffers are assigned (atomically)
                    processedFrameSize.store(new_processed_frame_size);

                    buff_frame_length = new_processed_frame_size * sizeof(uint16_t);
                }
                
                // Clear the reallocation flag to allow threads to resume
                bufferReallocationInProgress.store(false);
            }

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case SET_MODE: {
            aditof::DepthSensorModeDetails aditofModeDetail;
            aditofModeDetail.modeNumber =
                buff_recv.mode_details().mode_number();
            aditofModeDetail.pixelFormatIndex =
                buff_recv.mode_details().pixel_format_index();
            aditofModeDetail.frameWidthInBytes =
                buff_recv.mode_details().frame_width_in_bytes();
            aditofModeDetail.frameHeightInBytes =
                buff_recv.mode_details().frame_height_in_bytes();
            aditofModeDetail.baseResolutionWidth =
                buff_recv.mode_details().base_resolution_width();
            aditofModeDetail.baseResolutionHeight =
                buff_recv.mode_details().base_resolution_height();
            aditofModeDetail.metadataSize =
                buff_recv.mode_details().metadata_size();

            for (int i = 0; i < buff_recv.mode_details().frame_content_size();
                 i++) {
                aditofModeDetail.frameContent.emplace_back(
                    buff_recv.mode_details().frame_content(i));
            }

            aditof::Status status = camDepthSensor->setMode(aditofModeDetail);

            if (status == aditof::Status::OK) {
                int width_tmp = aditofModeDetail.baseResolutionWidth;
                int height_tmp = aditofModeDetail.baseResolutionHeight;

                if (aditofModeDetail.isPCM) {
                    processedFrameSize = width_tmp * height_tmp *
                                         aditofModeDetail.numberOfPhases;
                } else {
                    processedFrameSize = width_tmp * height_tmp * 4;
                }

                // Lock frameMutex to ensure threads aren't using the buffers
                // Also reset the frame capture state to avoid race conditions
                {
                    std::lock_guard<std::mutex> lock(frameMutex);
                    
                    // Reset frame state flags
                    frameCaptured = false;
                    goCaptureFrame = false;
                    
                    // Create new buffers before releasing old ones
                    auto new_buff_frame_to_send = std::shared_ptr<uint16_t[]>(new uint16_t[processedFrameSize], std::default_delete<uint16_t[]>());
                    auto new_buff_frame_to_be_captured = std::shared_ptr<uint16_t[]>(new uint16_t[processedFrameSize], std::default_delete<uint16_t[]>());
                    
                    // Now assign them (old buffers will be freed only when all references are gone)
                    buff_frame_to_send = new_buff_frame_to_send;
                    buff_frame_to_be_captured = new_buff_frame_to_be_captured;

                    buff_frame_length = processedFrameSize * 2;
                }
            }

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case GET_AVAILABLE_CONTROLS: {
            std::vector<std::string> aditofControls;

            aditof::Status status =
                camDepthSensor->getAvailableControls(aditofControls);
            for (const auto &aditofControl : aditofControls) {
                buff_send.add_strings_payload(aditofControl);
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case SET_CONTROL: {
            std::string controlName = buff_recv.func_strings_param(0);
            std::string controlValue = buff_recv.func_strings_param(1);
            aditof::Status status =
                camDepthSensor->setControl(controlName, controlValue);
            if (controlName == "netlinktest") {
                sameFrameEndlessRepeat = controlValue == "1";
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case GET_CONTROL: {
            std::string controlName = buff_recv.func_strings_param(0);
            std::string controlValue;
            aditof::Status status =
                camDepthSensor->getControl(controlName, controlValue);
            buff_send.add_strings_payload(controlValue);
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case SET_SENSOR_CONFIGURATION: {
            std::string sensorConf = buff_recv.func_strings_param(0);
            aditof::Status status =
                camDepthSensor->setSensorConfiguration(sensorConf);
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case INIT_TARGET_DEPTH_COMPUTE: {
            aditof::Status status = camDepthSensor->initTargetDepthCompute(
                (uint8_t *)buff_recv.func_bytes_param(0).c_str(),
                static_cast<uint16_t>(buff_recv.func_int32_param(0)),
                (uint8_t *)buff_recv.func_bytes_param(1).c_str(),
                static_cast<uint16_t>(buff_recv.func_int32_param(1)));

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_READ_CMD: {
            uint16_t cmd = static_cast<uint16_t>(buff_recv.func_int32_param(0));
            uint16_t data;
            unsigned int usDelay =
                static_cast<unsigned int>(buff_recv.func_int32_param(1));

            aditof::Status status =
                camDepthSensor->adsd3500_read_cmd(cmd, &data, usDelay);
            if (status == aditof::Status::OK) {
                buff_send.add_int32_payload(static_cast<::google::int32>(data));
            }

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_WRITE_CMD: {
            uint16_t cmd = static_cast<uint16_t>(buff_recv.func_int32_param(0));
            uint16_t data =
                static_cast<uint16_t>(buff_recv.func_int32_param(1));
            uint32_t usDelay =
                static_cast<uint32_t>(buff_recv.func_int32_param(2));

            aditof::Status status =
                camDepthSensor->adsd3500_write_cmd(cmd, data, usDelay);
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_READ_PAYLOAD_CMD: {
            uint32_t cmd = static_cast<uint32_t>(buff_recv.func_int32_param(0));
            uint16_t payload_len =
                static_cast<uint16_t>(buff_recv.func_int32_param(1));
            uint8_t *data = new uint8_t[payload_len];

            memcpy(data, buff_recv.func_bytes_param(0).c_str(),
                   4 * sizeof(uint8_t));
            aditof::Status status = camDepthSensor->adsd3500_read_payload_cmd(
                cmd, data, payload_len);
            if (status == aditof::Status::OK) {
                buff_send.add_bytes_payload(data, payload_len);
            }

            delete[] data;
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_READ_PAYLOAD: {
            uint16_t payload_len =
                static_cast<uint16_t>(buff_recv.func_int32_param(0));
            uint8_t *data = new uint8_t[payload_len];

            aditof::Status status =
                camDepthSensor->adsd3500_read_payload(data, payload_len);
            if (status == aditof::Status::OK) {
                buff_send.add_bytes_payload(data, payload_len);
            }

            delete[] data;
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_WRITE_PAYLOAD_CMD: {
            uint32_t cmd = static_cast<uint32_t>(buff_recv.func_int32_param(0));
            uint16_t payload_len =
                static_cast<uint16_t>(buff_recv.func_int32_param(1));
            uint8_t *data = new uint8_t[payload_len];

            memcpy(data, buff_recv.func_bytes_param(0).c_str(), payload_len);
            aditof::Status status = camDepthSensor->adsd3500_write_payload_cmd(
                cmd, data, payload_len);

            delete[] data;
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_WRITE_PAYLOAD: {
            uint16_t payload_len =
                static_cast<uint16_t>(buff_recv.func_int32_param(0));
            uint8_t *data = new uint8_t[payload_len];

            memcpy(data, buff_recv.func_bytes_param(0).c_str(), payload_len);
            aditof::Status status =
                camDepthSensor->adsd3500_write_payload(data, payload_len);

            delete[] data;
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case ADSD3500_GET_STATUS: {
            int chipStatus;
            int imagerStatus;

            aditof::Status status =
                camDepthSensor->adsd3500_get_status(chipStatus, imagerStatus);
            if (status == aditof::Status::OK) {
                buff_send.add_int32_payload(chipStatus);
                buff_send.add_int32_payload(imagerStatus);
            }

            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case GET_INTERRUPTS: {

            {
                if (adsd3500InterruptsQueueMutex.try_lock_for(
                        std::chrono::milliseconds(500))) {
                    while (!adsd3500InterruptsQueue.empty()) {
                        buff_send.add_int32_payload(
                            (int)adsd3500InterruptsQueue.front());
                        adsd3500InterruptsQueue.pop();
                    }
                    adsd3500InterruptsQueueMutex.unlock();
                } else {
                    LOG(ERROR) << "Unable to lock adsd3500InterruptsQueueMutex "
                                  "in 500 ms";
                }
            }

            buff_send.set_status(
                static_cast<::payload::Status>(aditof::Status::OK));
            break;
        }

        case HANG_UP: {
            if (sensors_are_created) {
                cleanup_sensors();
            }
            clientEngagedWithSensors = false;

            break;
        }

        case GET_DEPTH_COMPUTE_PARAM: {
            std::map<std::string, std::string> ini_params;
            aditof::Status status =
                camDepthSensor->getDepthComputeParams(ini_params);
            if (status == aditof::Status::OK) {
                buff_send.add_strings_payload(ini_params["abThreshMin"]);
                buff_send.add_strings_payload(ini_params["abSumThresh"]);
                buff_send.add_strings_payload(ini_params["confThresh"]);
                buff_send.add_strings_payload(ini_params["radialThreshMin"]);
                buff_send.add_strings_payload(ini_params["radialThreshMax"]);
                buff_send.add_strings_payload(ini_params["jblfApplyFlag"]);
                buff_send.add_strings_payload(ini_params["jblfWindowSize"]);
                buff_send.add_strings_payload(ini_params["jblfGaussianSigma"]);
                buff_send.add_strings_payload(
                    ini_params["jblfExponentialTerm"]);
                buff_send.add_strings_payload(ini_params["jblfMaxEdge"]);
                buff_send.add_strings_payload(ini_params["jblfABThreshold"]);
                buff_send.add_strings_payload(ini_params["headerSize"]);
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case SET_DEPTH_COMPUTE_PARAM: {
            std::map<std::string, std::string> ini_params;
            ini_params["abThreshMin"] = buff_recv.func_strings_param(0);
            ini_params["abSumThresh"] = buff_recv.func_strings_param(1);
            ini_params["confThresh"] = buff_recv.func_strings_param(2);
            ini_params["radialThreshMin"] = buff_recv.func_strings_param(3);
            ini_params["radialThreshMax"] = buff_recv.func_strings_param(4);
            ini_params["jblfApplyFlag"] = buff_recv.func_strings_param(5);
            ini_params["jblfWindowSize"] = buff_recv.func_strings_param(6);
            ini_params["jblfGaussianSigma"] = buff_recv.func_strings_param(7);
            ini_params["jblfExponentialTerm"] = buff_recv.func_strings_param(8);
            ini_params["jblfMaxEdge"] = buff_recv.func_strings_param(9);
            ini_params["jblfABThreshold"] = buff_recv.func_strings_param(10);

            aditof::Status status =
                camDepthSensor->setDepthComputeParams(ini_params);
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }

        case GET_INI_ARRAY: {
            int mode = buff_recv.func_int32_param(0);
            std::string iniStr;

            aditof::Status status =
                camDepthSensor->getIniParamsArrayForMode(mode, iniStr);

            if (status == aditof::Status::OK) {
                buff_send.add_strings_payload(iniStr);
            }
            buff_send.set_status(static_cast<::payload::Status>(status));
            break;
        }
        case SERVER_CONNECT: {
            if (!no_of_client_connected) {
                buff_send.set_message("Connection Allowed");
            } else {
                buff_send.set_message("Only 1 client connection allowed");
            }
            break;
        }

        default: {
            std::string msgErr = "Function not found";
            std::cout << msgErr << "\n";

            buff_send.set_message(msgErr);
            buff_send.set_server_status(
                ::payload::ServerStatus::REQUEST_UNKNOWN);
            break;
        }
        } // switch
    } else {
        LOG(ERROR) << "Unknown function name : " << buff_recv.func_name();
    }

    {
        if (adsd3500InterruptsQueueMutex.try_lock_for(
                std::chrono::milliseconds(500))) {
            buff_send.set_interrupt_occured(!adsd3500InterruptsQueue.empty());
            adsd3500InterruptsQueueMutex.unlock();
        } else {
            LOG(ERROR)
                << "Unable to lock adsd3500InterruptsQueueMutex in 500 ms";
        }
    }

    buff_recv.Clear();
}

void Initialize() {
    s_map_api_Values["FindSensors"] = FIND_SENSORS;
    s_map_api_Values["Open"] = OPEN;
    s_map_api_Values["Start"] = START;
    s_map_api_Values["Stop"] = STOP;
    s_map_api_Values["GetAvailableModes"] = GET_AVAILABLE_MODES;
    s_map_api_Values["GetModeDetails"] = GET_MODE_DETAILS;
    s_map_api_Values["SetModeByIndex"] = SET_MODE_BY_INDEX;
    s_map_api_Values["SetMode"] = SET_MODE;
    //s_map_api_Values["GetFrame"] = GET_FRAME;
    s_map_api_Values["GetAvailableControls"] = GET_AVAILABLE_CONTROLS;
    s_map_api_Values["SetControl"] = SET_CONTROL;
    s_map_api_Values["GetControl"] = GET_CONTROL;
    s_map_api_Values["SetSensorConfiguration"] = SET_SENSOR_CONFIGURATION;
    s_map_api_Values["InitTargetDepthCompute"] = INIT_TARGET_DEPTH_COMPUTE;
    s_map_api_Values["Adsd3500ReadCmd"] = ADSD3500_READ_CMD;
    s_map_api_Values["Adsd3500WriteCmd"] = ADSD3500_WRITE_CMD;
    s_map_api_Values["Adsd3500ReadPayloadCmd"] = ADSD3500_READ_PAYLOAD_CMD;
    s_map_api_Values["Adsd3500ReadPayload"] = ADSD3500_READ_PAYLOAD;
    s_map_api_Values["Adsd3500WritePayloadCmd"] = ADSD3500_WRITE_PAYLOAD_CMD;
    s_map_api_Values["Adsd3500WritePayload"] = ADSD3500_WRITE_PAYLOAD;
    s_map_api_Values["Adsd3500GetStatus"] = ADSD3500_GET_STATUS;
    s_map_api_Values["GetInterrupts"] = GET_INTERRUPTS;
    s_map_api_Values["HangUp"] = HANG_UP;
    s_map_api_Values["GetDepthComputeParam"] = GET_DEPTH_COMPUTE_PARAM;
    s_map_api_Values["SetDepthComputeParam"] = SET_DEPTH_COMPUTE_PARAM;
    s_map_api_Values["GetIniArray"] = GET_INI_ARRAY;
    s_map_api_Values["ServerConnect"] = SERVER_CONNECT;
}
