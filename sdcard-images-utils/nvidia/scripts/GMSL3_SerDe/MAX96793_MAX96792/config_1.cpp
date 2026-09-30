/*
# Name: SPadmana
# Date: 9/10/2026
# Version: 1.6.2
#
# I2C Address(0x), Register Address(0x), Register Value(0x), Read Modify Write(0x)
#
# THIS DATA FILE, AND ALL INFORMATION CONTAINED THEREIN,
# IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL ANALOG DEVICES, INC. BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE DATA FILE,
# THE INFORMATION CONTAINED THEREIN, OR ITS USE FOR ANY PURPOSE.
# BEFORE USING THIS DATA FILE IN ANY APPLICATION FOR PRODUCTION OR DEPLOYMENT,
# THE CUSTOMER IS SOLELY RESPONSIBLE FOR TESTING AND VERIFYING
# THE CONTENT OF THIS DATA FILE IN CONNECTION WITH THEIR PRODUCTS AND SYSTEM(S).
# ---------------------------------------------------------------------------------
#
#            _____ _____  
#      /\   |  __ \_   _| 
#     /  \  | |  | || |   
#    / /\ \ | |  | || |   
#   / ____ \| |__| || |_  
#  /_/    \_\_____/_____| 
#
# ---------------------------------------------------------------------------------
*/
/*
# This script is validated on: 
# MAX96793
# MAX96792A
# Please refer to the Errata sheet for each device.
# ---------------------------------------------------------------------------------
*/
//  
// CSIConfigurationTool
//  
// GMSL-A / Serializer: MAX96793 (Tunnel Mode) / Mode: 1x4 / Device Address: 0x80 / Multiple-VC Case: Single VC / Pipe Sharing: Separate Pipes
// PipeZ:
// Input Stream: VC0 RAW8 PortB (D-PHY)

// Deserializer: MAX96792A / Mode: 2 (1x4) / Device Address: 0x54
// PipeY:
// GMSL-A Input Stream: VC0 RAW8 PortB - Output Stream: VC0 RAW8 PortA (D-PHY)

0x04,0x54,0x03,0x13,0x00, // BACKTOP : BACKTOP12 | CSI_OUT_EN (CSI_OUT_EN): CSI output disabled
// Link Initialization for Deserializer
0x04,0x54,0x00,0x10,0x01, // TCTRL : CTRL0 | AUTO_LINK (AUTO_LINK): Disabled
0x04,0x55,0x00,0x01,0x03,0x03, // DEV : REG1 | RX_RATE (RX_RATE_PHYA): 12
0x04,0x55,0x00,0x04,0x40,0x40, // DEV : REG4 | GMSL3_A (GMSL3_A): Enabled
0x04,0x55,0x00,0x06,0x10,0x10, // DEV : REG6 | I2CSEL (I2CSEL): I2C
0x04,0x54,0x0F,0x00,0x01, // GMSL1_COMMON : GMSL1_EN | (Default) LINK_EN_A (LINK_EN_A): Enabled | LINK_EN_B (LINK_EN_B): Disabled
0x04,0x54,0x00,0x10,0x21, // TCTRL : CTRL0 | (Default) LINK_CFG (LINK_CFG): 0x1 | RESET_ONESHOT (RESET_ONESHOT LINK A): Activated
0x00,0x78, // 120 msec delay
// Link Initialization for Deserializer
0x04,0x54,0x00,0x01,0x03, // DEV : REG1 | (Default) DIS_REM_CC (GMSL Link A I2C Port 0): Enabled
0x04,0x54,0x00,0x03,0x57, // DEV : REG3 | DIS_REM_CC_B (GMSL Link B I2C Port 0): Disabled
0x00,0x01, // Warning: The actual recommended delay is 5 usec.
// Video Transmit Configuration for Serializer(s)
0x04,0x80,0x00,0x02,0x03, // DEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Disabled
//  
// INSTRUCTIONS FOR GMSL-A SERIALIZER MAX96793
//  
// MIPI D-PHY Configuration
0x04,0x80,0x03,0x30,0x00, // MIPI_RX : MIPI_RX0 | (Default) RSVD (Port Configuration): 1x4
0x04,0x80,0x03,0x83,0x80, // MIPI_RX_EXT : EXT11 | (Default) Tun_Mode (Tunnel Mode): Enabled
0x04,0x80,0x03,0x31,0x10, // MIPI_RX : MIPI_RX1 | ctrl1_num_lanes (Port B - Lane Count): 2
0x04,0x80,0x03,0x32,0xE0, // MIPI_RX : MIPI_RX2 | (Default) phy1_lane_map (Lane Map - PHY1 D0): Lane 2 | (Default) phy1_lane_map (Lane Map - PHY1 D1): Lane 3
0x04,0x80,0x03,0x33,0x04, // MIPI_RX : MIPI_RX3 | (Default) phy2_lane_map (Lane Map - PHY2 D0): Lane 0 | (Default) phy2_lane_map (Lane Map - PHY2 D1): Lane 1
0x04,0x80,0x03,0x34,0x00, // MIPI_RX : MIPI_RX4 | (Default) phy1_pol_map (Polarity - PHY1 Lane 0): Normal | (Default) phy1_pol_map (Polarity - PHY1 Lane 1): Normal
0x04,0x80,0x03,0x35,0x00, // MIPI_RX : MIPI_RX5 | (Default) phy2_pol_map (Polarity - PHY2 Lane 0): Normal | (Default) phy2_pol_map (Polarity - PHY2 Lane 1): Normal | (Default) phy2_pol_map (Polarity - PHY2 Clock Lane): Normal
// Controller to Pipe Mapping Configuration
0x04,0x80,0x03,0x08,0x64, // FRONTTOP : FRONTTOP_0 | (Default) RSVD (CLK_SELZ): Port B | (Default) START_PORTB (START_PORTB): Enabled
0x04,0x80,0x03,0x11,0x40, // FRONTTOP : FRONTTOP_9 | (Default) START_PORTBZ (START_PORTBZ): Start Video
// Pipe Configuration
0x04,0x80,0x00,0x5B,0x00, // CFGV__VIDEO_Z : TX3 | TX_STR_SEL (TX_STR_SEL Pipe Z): 0x0
//  
// INSTRUCTIONS FOR DESERIALIZER MAX96792A
//  
// Video Pipes And Routing Configuration
0x04,0x54,0x01,0x61,0x30, // VIDEO_PIPE_SEL : VIDEO_PIPE_SEL | VIDEO_PIPE_SEL_Y (STR_SELY): Link A Stream Id 0
// MIPI D-PHY Configuration
0x04,0x54,0x03,0x30,0x04, // MIPI_PHY : MIPI_PHY0 | (Default) phy_4x2 (Port Configuration): 2 (1x4)
0x04,0x54,0x04,0x4A,0x50, // MIPI_TX__1 : MIPI_TX10 | CSI2_LANE_CNT (Port A - Lane Count): 2
0x04,0x54,0x03,0x33,0x4E, // MIPI_PHY : MIPI_PHY3 | (Default) phy0_lane_map (Lane Map - PHY0 D0): Lane 2 | (Default) phy0_lane_map (Lane Map - PHY0 D1): Lane 3 | (Default) phy1_lane_map (Lane Map - PHY1 D0): Lane 0 | (Default) phy1_lane_map (Lane Map - PHY1 D1): Lane 1
0x04,0x54,0x03,0x35,0x00, // MIPI_PHY : MIPI_PHY5 | (Default) phy0_pol_map (Polarity - PHY0 Lane 0): Normal | (Default) phy0_pol_map (Polarity - PHY0 Lane 1): Normal | (Default) phy1_pol_map (Polarity - PHY1 Lane 0): Normal | (Default) phy1_pol_map (Polarity - PHY1 Lane 1): Normal | (Default) phy1_pol_map (Polarity - PHY1 Clock Lane): Normal
0x04,0x54,0x1D,0x00,0xF4, // DPLL__CSI2 : DPLL_0 | config_soft_rst_n (config_soft_rst_n - PHY1): 0x0
// This is to set predefined (coarse) CSI output frequency
// CSI Phy 1 is 800 Mbps/lane.
0x04,0x54,0x1D,0x00,0xF4, // DPLL__CSI2 : DPLL_0 | (Default) 
0x04,0x54,0x03,0x20,0x28,
0x04,0x54,0x1D,0x00,0xF5, // DPLL__CSI2 : DPLL_0 |  | (Default) config_soft_rst_n (config_soft_rst_n - PHY1): 0x1
0x04,0x54,0x03,0x32,0x34, // MIPI_PHY : MIPI_PHY2 | phy_Stdby_n (phy_Stdby_2): Put PHY2 in standby mode | phy_Stdby_n (phy_Stdby_3): Put PHY3 in standby mode
// Tunnel Mode Configuration
0x04,0x54,0x04,0x74,0x09, // MIPI_TX__1 : MIPI_TX52 | (Default) TUN_DEST (Tunneling Destination Pipe Y): 1 | TUN_EN (Pipe Y Tunnel Mode): Enabled
0x04,0x54,0x03,0x13,0x02, // BACKTOP : BACKTOP12 | CSI_OUT_EN (CSI_OUT_EN): CSI output enabled
// Video Transmit Configuration for Serializer(s)
0x04,0x80,0x00,0x02,0x43, // DEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Enabled
