/*****************************************************************************
*
* Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
* This software is proprietary & confidential to Analog Devices, Inc.
* and its licensors.
*****************************************************************************
*******************************************************************************
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.*/

#ifndef ADSD3500_INTERRUPT_NOTIFIER_H
#define ADSD3500_INTERRUPT_NOTIFIER_H

#include <iostream>
#include <memory>
#include <signal.h>
#include <sys/ioctl.h>
#include <vector>

class Adsd3500;

/**
 * @brief Singleton class for managing ADSD3500 hardware interrupt notifications
 *
 * This class handles interrupt delivery from the ADSD3500 device via the
 * /proc/adsd3500/value interface. It allows multiple sensors to subscribe
 * for interrupt notifications.
 */
class Adsd3500InterruptNotifier {
  public:
    /**
     * @brief Get the singleton instance
     * @return Reference to the singleton instance
     */
    static Adsd3500InterruptNotifier &getInstance();

    /**
     * @brief Signal event handler for ADSD3500 interrupts
     * @param n Signal number
     * @param info Signal information structure
     * @param unused Unused context parameter
     */
    static void signalEventHandler(int n, siginfo_t *info, void *unused);

    /**
     * @brief Enable hardware interrupt notifications
     * @return 0 on success, negative error code on failure
     */
    int enableInterrupts();

    /**
     * @brief Disable hardware interrupt notifications
     * @return 0 on success, negative error code on failure
     */
    int disableInterrupts();

    /**
     * @brief Check if interrupts are available
     * @return true if interrupts are enabled and available, false otherwise
     */
    bool interruptsAvailable();

    /**
     * @brief Subscribe a sensor to receive interrupt notifications
     * @param sensor Weak pointer to the sensor object
     */
    void subscribeSensor(std::weak_ptr<Adsd3500> sensor);

    /**
     * @brief Unsubscribe a sensor from interrupt notifications
     * @param sensor Weak pointer to the sensor object
     */
    void unsubscribeSensor(std::weak_ptr<Adsd3500> sensor);

  private:
    Adsd3500InterruptNotifier() {}
    static std::vector<std::weak_ptr<Adsd3500>> m_sensors;
    bool m_interruptsAvailable = false;
};

#endif // ADSD3500_INTERRUPT_NOTIFIER_H
