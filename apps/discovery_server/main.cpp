#include "discovery_server.h"
#include "platform.h"
#include <iostream>
#include <csignal>
#include <cstring>
#include <memory>
#include <fstream>
#include <sstream>

using namespace network_discovery;

std::unique_ptr<DiscoveryServer> g_server;

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\nReceived signal " << signal << ", shutting down..." << std::endl;
        if (g_server) {
            g_server->stop();
        }
    }
}

// Simple JSON parser to extract serial number
std::string read_serial_from_json(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Could not open config file: " << filename << std::endl;
        return "";
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    
    // Simple parser to find "serial_number": "value"
    size_t pos = content.find("\"serial_number\"");
    if (pos == std::string::npos) {
        std::cerr << "Error: 'serial_number' field not found in JSON" << std::endl;
        return "";
    }
    
    // Find the colon after the key
    pos = content.find(':', pos);
    if (pos == std::string::npos) return "";
    
    // Find the opening quote of the value
    pos = content.find('\"', pos);
    if (pos == std::string::npos) return "";
    pos++; // Move past the opening quote
    
    // Find the closing quote
    size_t end_pos = content.find('\"', pos);
    if (end_pos == std::string::npos) return "";
    
    return content.substr(pos, end_pos - pos);
}

// Helper to extract string value from JSON
std::string extract_json_string(const std::string& content, const std::string& key) {
    size_t pos = content.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    
    pos = content.find(':', pos);
    if (pos == std::string::npos) return "";
    
    pos = content.find('\"', pos);
    if (pos == std::string::npos) return "";
    pos++;
    
    size_t end_pos = content.find('\"', pos);
    if (end_pos == std::string::npos) return "";
    
    return content.substr(pos, end_pos - pos);
}

// Read interface from JSON config file
std::string read_interface_from_json(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        return "";
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    
    return extract_json_string(content, "interface");
}

// Read network configuration from JSON
bool read_network_config_from_json(const std::string& filename,
                                   std::string& mode,
                                   NetworkConfig& config) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        return false;
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    
    // Read network_mode
    std::string mode_str = extract_json_string(content, "network_mode");
    if (mode_str == "static") {
        mode = "static";
    } else if (mode_str == "dhcp_server") {
        mode = "dhcp_server";
    } else {
        mode = "dhcp";
    }
    
    // Read static IP config
    config.ip_address = extract_json_string(content, "ip_address");
    config.netmask = extract_json_string(content, "netmask");
    config.gateway = extract_json_string(content, "gateway");
    
    // Read DHCP server config if in dhcp_server mode
    if (mode == "dhcp_server") {
        config.dhcp_range_start = extract_json_string(content, "range_start");
        config.dhcp_range_end = extract_json_string(content, "range_end");
    }
    
    return true;
}

void print_usage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [OPTIONS]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -p, --port PORT        Port to listen on (default: " 
              << DEFAULT_DISCOVERY_PORT << ")" << std::endl;
    std::cout << "  -c, --config FILE      JSON config file with serial_number and network settings" << std::endl;
    std::cout << "  -i, --interface IFACE  Network interface to use (default: auto-detect)" << std::endl;
    std::cout << "  -h, --help             Show this help message" << std::endl;
    std::cout << std::endl;
    std::cout << "Network Discovery Server" << std::endl;
    std::cout << "Listens for discovery requests and responds with server information." << std::endl;
    std::cout << "Allows clients to query and configure network settings." << std::endl;
    std::cout << std::endl;
    std::cout << "  Config file format (JSON):" << std::endl;
    std::cout << "  {" << std::endl;
    std::cout << "    \"serial_number\": \"DEV-12345\"," << std::endl;
    std::cout << "    \"interface\": \"eth0\"," << std::endl;
    std::cout << "    \"network_mode\": \"dhcp\",  // or \"static\" or \"dhcp_server\"" << std::endl;
    std::cout << "    \"static_ip\": {" << std::endl;
    std::cout << "      \"ip_address\": \"192.168.1.100\"," << std::endl;
    std::cout << "      \"netmask\": \"255.255.255.0\"," << std::endl;
    std::cout << "      \"gateway\": \"192.168.1.1\"" << std::endl;
    std::cout << "    }," << std::endl;
    std::cout << "    \"dhcp_server\": {  // only for dhcp_server mode" << std::endl;
    std::cout << "      \"range_start\": \"192.168.1.100\"," << std::endl;
    std::cout << "      \"range_end\": \"192.168.1.200\"" << std::endl;
    std::cout << "    }" << std::endl;
    std::cout << "  }" << std::endl;
    std::cout << std::endl;
    std::cout << "Note: Root privileges are required to apply and change network configuration." << std::endl;
}

int main(int argc, char* argv[]) {
    uint16_t port = DEFAULT_DISCOVERY_PORT;
    std::string config_file;
    std::string interface;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "-p") == 0 || std::strcmp(argv[i], "--port") == 0) {
            if (i + 1 < argc) {
                port = static_cast<uint16_t>(std::atoi(argv[++i]));
            } else {
                std::cerr << "Error: --port requires an argument" << std::endl;
                return 1;
            }
        } else if (std::strcmp(argv[i], "-c") == 0 || std::strcmp(argv[i], "--config") == 0) {
            if (i + 1 < argc) {
                config_file = argv[++i];
            } else {
                std::cerr << "Error: --config requires an argument" << std::endl;
                return 1;
            }
        } else if (std::strcmp(argv[i], "-i") == 0 || std::strcmp(argv[i], "--interface") == 0) {
            if (i + 1 < argc) {
                interface = argv[++i];
            } else {
                std::cerr << "Error: --interface requires an argument" << std::endl;
                return 1;
            }
        } else if (std::strcmp(argv[i], "-h") == 0 || std::strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            std::cerr << "Unknown option: " << argv[i] << std::endl;
            print_usage(argv[0]);
            return 1;
        }
    }
    
    // Initialize platform networking
    if (!Platform::initialize_networking()) {
        std::cerr << "Failed to initialize networking" << std::endl;
        return 1;
    }
    
    // Setup signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);
    
    std::cout << "=== Network Discovery Server ===" << std::endl;
    std::cout << std::endl;
    
    if (!NetworkUtils::has_root_privileges()) {
        std::cout << "WARNING: Not running with administrator privileges." << std::endl;
        std::cout << "Network configuration changes will not be available." << std::endl;
#ifdef PLATFORM_WINDOWS
        std::cout << "Run as Administrator to enable full functionality." << std::endl;
#else
        std::cout << "Run with sudo to enable full functionality." << std::endl;
#endif
        std::cout << std::endl;
    }
    
    // Read serial number from config file if provided
    std::string serial_number;
    std::string network_mode = "dhcp";
    NetworkConfig static_config = {"", "", ""};
    std::string config_interface;
    
    if (!config_file.empty()) {
        serial_number = read_serial_from_json(config_file);
        if (serial_number.empty()) {
            std::cerr << "Failed to read serial number from config file" << std::endl;
            std::cerr << "Will generate a random serial number instead" << std::endl;
            std::cout << std::endl;
        }
        
        // Read network configuration
        if (read_network_config_from_json(config_file, network_mode, static_config)) {
            std::cout << "Network configuration loaded from config file:" << std::endl;
            std::cout << "  Mode: " << network_mode << std::endl;
            if (network_mode == "static") {
                std::cout << "  IP Address: " << static_config.ip_address << std::endl;
                std::cout << "  Netmask: " << static_config.netmask << std::endl;
                std::cout << "  Gateway: " << static_config.gateway << std::endl;
            } else if (network_mode == "dhcp_server") {
                std::cout << "  Server IP: " << static_config.ip_address << std::endl;
                std::cout << "  Netmask: " << static_config.netmask << std::endl;
                std::cout << "  Gateway: " << static_config.gateway << std::endl;
                std::cout << "  DHCP Range: " << static_config.dhcp_range_start 
                          << " - " << static_config.dhcp_range_end << std::endl;
            }
            std::cout << std::endl;
        }
        
        // Read interface from config (CLI argument takes precedence)
        if (interface.empty()) {
            config_interface = read_interface_from_json(config_file);
            if (!config_interface.empty()) {
                interface = config_interface;
                std::cout << "Using interface from config file: " << interface << std::endl;
                std::cout << std::endl;
            }
        }
    }
    
    // Create and start server
    g_server = std::make_unique<DiscoveryServer>(port, serial_number, config_file, interface);
    
    if (!g_server->start()) {
        std::cerr << "Failed to start server" << std::endl;
        Platform::cleanup_networking();
        return 1;
    }
    
    // Apply network configuration if loaded from config
    if (!config_file.empty() && !network_mode.empty()) {
        if (NetworkUtils::has_root_privileges()) {
            std::cout << "Applying network configuration from config file..." << std::endl;
            NetworkMode mode;
            if (network_mode == "dhcp") {
                mode = NetworkMode::DHCP;
            } else if (network_mode == "static") {
                mode = NetworkMode::STATIC;
            } else {
                mode = NetworkMode::DHCP_SERVER;
            }
            g_server->apply_network_config(mode, static_config);
            std::cout << std::endl;
        } else {
            std::cout << "Skipping network configuration (requires root privileges)" << std::endl;
            std::cout << std::endl;
        }
    }
    
    std::cout << std::endl;
    std::cout << "Press Ctrl+C to stop the server" << std::endl;
    std::cout << std::endl;
    
    // Wait for server to stop
    while (g_server->is_running()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    
    Platform::cleanup_networking();
    return 0;
}
