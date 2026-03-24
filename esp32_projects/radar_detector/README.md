# CoD-Style Detection Radar

An ESP32-powered rotating ultrasonic radar with a real-time green radar display — inspired by the minimap radar from Call of Duty.

## Hardware

| Component | Model | Purpose |
|---|---|---|
| Microcontroller | ESP32 DevKit | Brain + processing |
| Distance Sensor | HC-SR04 | Detect objects |
| Servo Motor | SG90 | Rotate sensor 0–180° |
| TFT Display | ILI9341 240×320 | Radar visualization |
| Buzzer | Passive 5V | Close-range alert |

## Wiring

```
HC-SR04
  TRIG  → GPIO 26
  ECHO  → GPIO 25
  VCC   → 5V
  GND   → GND

SG90 Servo
  Signal → GPIO 27
  VCC    → 5V
  GND    → GND

ILI9341 TFT (SPI)
  MOSI → GPIO 23 (SPI MOSI)
  SCLK → GPIO 18 (SPI CLK)
  CS   → GPIO  5
  DC   → GPIO  2
  RST  → GPIO  4
  LED  → 3.3V
  VCC  → 3.3V
  GND  → GND

Buzzer
  +    → GPIO 32
  -    → GND
```

## Libraries (install via Arduino Library Manager)

- `Adafruit GFX Library`
- `Adafruit ILI9341`
- `ESP32Servo`

## How It Works

1. The SG90 servo sweeps the HC-SR04 from 0° to 180° and back
2. At each angle step (2°), the sensor fires an ultrasonic pulse
3. Detected distances are converted to polar → screen coordinates
4. The TFT renders a classic green radar with:
   - Rotating sweep line
   - Concentric range rings (labeled in cm)
   - Bright blips where objects are detected
   - Faded trail of previous sweep positions
5. Objects closer than 40 cm trigger a buzzer alert

## Display Layout

```
┌────────────────────┐
│       RADAR        │
│   .  ·  90  ·  .   │
│  ·  ·  · | ·  ·  · │
│ ·  [blip]·|·       │
│·  · ·  ·  |  · ·  ·│
│180─────────────────0│
│ Angle: 74°         │
│ Dist:  62 cm       │
└────────────────────┘
```

## Config

Edit these constants at the top of `radar_detector.ino`:

| Constant | Default | Description |
|---|---|---|
| `RADAR_MAX_DIST_CM` | 150 | Detection range (cm) |
| `RADAR_ANGLE_STEP` | 2 | Degrees per servo step |
| `SWEEP_DELAY_MS` | 8 | Speed of sweep |
| `ALERT_DIST_CM` | 40 | Buzzer trigger distance |

## Upgrading Ideas

- **360° sweep**: Use a continuous rotation servo + slip ring
- **WiFi map**: Stream radar data to a browser via WebSocket
- **Multiple sensors**: Add a second HC-SR04 for vertical plane
- **PIR layer**: Add a PIR sensor for motion-only detection
- **OLED version**: Port to 128×64 OLED for smaller form factor
