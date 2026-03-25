# 6-DOF IMU Dashboard

Ready-to-use Serial Studio project for 6-axis IMU sensors (accelerometer + gyroscope).

## Expected Data Format

Comma-separated values with frame delimiters:

```
$accelX,accelY,accelZ,gyroX,gyroY,gyroZ;
```

- Fields 1-3: Accelerometer X/Y/Z in **g**
- Fields 4-6: Gyroscope X/Y/Z in **deg/s**

## Dashboard Widgets

- **Accelerometer group** — 3D accelerometer widget with per-axis plots and FFT analysis (256 samples, 100 Hz)
- **Gyroscope group** — 3D gyroscope widget with per-axis plots
- **IMU Overview** — Data grid showing all 6 channels in a table

## Configuration

- Frame delimiters: `$` (start) `;` (end)
- Plot ranges: ±2g for accelerometer, ±250 deg/s for gyroscope
- FFT enabled on accelerometer channels for vibration analysis
- 200 data points per plot

## Compatible Sensors

Works with any 6-DOF IMU that outputs comma-separated data: MPU-6050, MPU-9250, ICM-20948, BMI160, LSM6DS3, etc.
