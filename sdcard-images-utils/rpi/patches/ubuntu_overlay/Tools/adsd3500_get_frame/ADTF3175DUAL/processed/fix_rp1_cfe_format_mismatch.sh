#!/bin/bash
# filepath: scripts/raspberry-pi/fix_rp1_cfe_format_mismatch.sh

# Fix RP1 CFE format validation errors
# Supports both RG12 (12-bit) and RGGB (8-bit) pixel formats

set -e

SENSOR_ENTITY="adsd3500 10-0038"
CSI2_ENTITY="csi2"
VIDEO_DEVICE="/dev/video0"

# Default to 12-bit format (can be overridden with -f flag)
PREFERRED_FORMAT="12bit"
PREFERRED_RESOLUTION="1024x4096"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse command line options
while getopts "f:r:h" opt; do
    case $opt in
        f)
            PREFERRED_FORMAT="$OPTARG"
            ;;
        r)
            PREFERRED_RESOLUTION="$OPTARG"
            ;;
        h)
            echo "Usage: $0 [-f format] [-r resolution]"
            echo "  -f format: '12bit' (RG12) or '8bit' (RGGB) [default: 12bit]"
            echo "  -r resolution: e.g., '1024x4096', '512x512' [default: 1024x4096]"
            echo ""
            echo "Examples:"
            echo "  $0                          # Use 12-bit, 1024x4096"
            echo "  $0 -f 8bit -r 512x512      # Use 8-bit, 512x512"
            exit 0
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "RP1 CFE Format Configuration"
echo "=========================================="
echo ""

# Find media device
log_info "Detecting ADSD3500 media device..."
MEDIA_DEVICE=""

for media_dev in /dev/media*; do
    if [ ! -c "$media_dev" ]; then
        continue
    fi
    if media-ctl -d "$media_dev" -p 2>/dev/null | grep -q "$SENSOR_ENTITY"; then
        MEDIA_DEVICE="$media_dev"
        break
    fi
done

if [ -z "$MEDIA_DEVICE" ]; then
    log_error "ADSD3500 sensor not found"
    exit 1
fi

log_success "Found ADSD3500 on $MEDIA_DEVICE"
echo ""

# Determine mediabus code and pixel format based on bit depth
case "$PREFERRED_FORMAT" in
    12bit|12|RG12)
        MBUS_CODE="SRGGB12_1X12"
        PIX_FORMATS=("RG12" "pRAA" "BA12" "SRGGB12P")
        BIT_DEPTH="12"
        ;;
    8bit|8|RGGB)
        MBUS_CODE="SRGGB8_1X8"
        PIX_FORMATS=("RGGB" "BA81" "GRBG")
        BIT_DEPTH="8"
        ;;
    *)
        log_error "Invalid format: $PREFERRED_FORMAT (use '12bit' or '8bit')"
        exit 1
        ;;
esac

# Parse resolution
WIDTH=$(echo "$PREFERRED_RESOLUTION" | cut -d'x' -f1)
HEIGHT=$(echo "$PREFERRED_RESOLUTION" | cut -d'x' -f2)

if [ -z "$WIDTH" ] || [ -z "$HEIGHT" ]; then
    log_error "Invalid resolution format: $PREFERRED_RESOLUTION (use WIDTHxHEIGHT)"
    exit 1
fi

log_info "Target configuration:"
echo "  Format: ${BIT_DEPTH}-bit Bayer ($MBUS_CODE)"
echo "  Resolution: ${WIDTH}x${HEIGHT}"
echo "  Pixel formats to try: ${PIX_FORMATS[*]}"
echo ""

# Verify format is supported
log_info "Verifying format support..."
SUPPORTED=false

for pixfmt in "${PIX_FORMATS[@]}"; do
    if v4l2-ctl -d "$VIDEO_DEVICE" --list-framesizes="$pixfmt" 2>/dev/null | grep -q "Size: Discrete ${WIDTH}x${HEIGHT}"; then
        SUPPORTED=true
        VERIFIED_PIXFMT="$pixfmt"
        log_success "Resolution ${WIDTH}x${HEIGHT} supported with format $pixfmt"
        break
    fi
done

if [ "$SUPPORTED" = false ]; then
    log_error "Resolution ${WIDTH}x${HEIGHT} not supported by sensor in ${BIT_DEPTH}-bit mode"
    echo ""
    log_info "Available resolutions for ${PIX_FORMATS[0]}:"
    v4l2-ctl -d "$VIDEO_DEVICE" --list-framesizes="${PIX_FORMATS[0]}" 2>/dev/null | grep "Size: Discrete" | head -10
    exit 1
fi

echo ""

# Configure media pipeline
log_info "Step 1: Reset media links..."
media-ctl -d "$MEDIA_DEVICE" -r 2>/dev/null || true
sleep 0.5

log_info "Step 2: Configure sensor format (${BIT_DEPTH}-bit Bayer)..."
media-ctl -d "$MEDIA_DEVICE" \
  -V "\"${SENSOR_ENTITY}\":0[fmt:${MBUS_CODE}/${WIDTH}x${HEIGHT} field:none colorspace:raw xfer:none ycbcr:601 quantization:full-range]"

log_info "Step 3: Configure CSI2 sink pad..."
media-ctl -d "$MEDIA_DEVICE" \
  -V "\"${CSI2_ENTITY}\":0[fmt:${MBUS_CODE}/${WIDTH}x${HEIGHT} field:none colorspace:raw xfer:none ycbcr:601 quantization:full-range]"

log_info "Step 4: Configure CSI2 source pad..."
media-ctl -d "$MEDIA_DEVICE" \
  -V "\"${CSI2_ENTITY}\":4[fmt:${MBUS_CODE}/${WIDTH}x${HEIGHT} field:none colorspace:raw xfer:none ycbcr:601 quantization:full-range]"

log_info "Step 5: Re-establish links..."
media-ctl -d "$MEDIA_DEVICE" \
  -l "\"${SENSOR_ENTITY}\":0->\"${CSI2_ENTITY}\":0[1]"

media-ctl -d "$MEDIA_DEVICE" \
  -l "\"${CSI2_ENTITY}\":4->\"rp1-cfe-csi2_ch0\":0[1]"

log_info "Step 6: Configure video device..."

SUCCESS=false
for PIX_FMT in "${PIX_FORMATS[@]}"; do
    log_info "  Trying pixel format: $PIX_FMT..."
    
    if v4l2-ctl -d "$VIDEO_DEVICE" --set-fmt-video=\
width=${WIDTH},\
height=${HEIGHT},\
pixelformat=${PIX_FMT},\
field=none,\
colorspace=raw 2>/dev/null; then
        log_success "  Video format set with: $PIX_FMT"
        SUCCESS=true
        FINAL_PIXFMT="$PIX_FMT"
        break
    else
        log_warn "  Format $PIX_FMT not accepted"
    fi
done

if [ "$SUCCESS" = false ]; then
    log_error "Could not set ${BIT_DEPTH}-bit format on video device"
    exit 1
fi

echo ""
log_info "Step 7: Verifying final configuration..."
echo "========================================"

echo "CSI2 pad 4 (source):"
media-ctl -d "$MEDIA_DEVICE" --get-v4l2 "\"${CSI2_ENTITY}\":4" | grep fmt

echo ""
echo "Video device format:"
v4l2-ctl -d "$VIDEO_DEVICE" --get-fmt-video | grep -E "Width|Pixel Format|Field|Colorspace"

echo "========================================"
echo ""

# Calculate expected frame size
if [ "$BIT_DEPTH" = "12" ]; then
    EXPECTED_SIZE=$((WIDTH * HEIGHT * 12 / 8))
    BYTES_PER_PIXEL="1.5"
else
    EXPECTED_SIZE=$((WIDTH * HEIGHT))
    BYTES_PER_PIXEL="1"
fi

log_success "Configuration complete!"
echo ""
log_info "Summary:"
echo "  Media device: $MEDIA_DEVICE"
echo "  Pixel format: $FINAL_PIXFMT (${BIT_DEPTH}-bit)"
echo "  Resolution: ${WIDTH}x${HEIGHT}"
echo "  Expected frame size: $EXPECTED_SIZE bytes ($BYTES_PER_PIXEL bytes/pixel)"
echo ""
log_info "Test capture:"
echo "  v4l2-ctl -d $VIDEO_DEVICE --stream-mmap --stream-count=1 --verbose"

exit 0
