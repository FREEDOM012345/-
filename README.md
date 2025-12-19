# SliderVR - Selenium Slider Captcha Solver

`SliderVR` is a Python utility class designed to automate the solving of slider captchas using Selenium and OpenCV. It calculates the gap position in the slider image and simulates human-like mouse movements to drag the slider to the correct position.

## Features

- **Automated Gap Detection**: Uses OpenCV's edge detection and template matching to accurately find the gap position in the background image.
- **Smart Scaling**: Automatically adjusts for differences between the rendered image size in the browser and the actual downloaded image size.
- **Human-like Movement**: Simulates realistic mouse movements with acceleration, deceleration, and random jitter to avoid bot detection.
- **Robust Error Handling**: Includes retry logic and detailed logging for debugging.

## Prerequisites

Before using this tool, ensure you have the following installed:

- Python 3.x
- [Selenium](https://pypi.org/project/selenium/)
- [OpenCV (opencv-python)](https://pypi.org/project/opencv-python/)
- A compatible WebDriver (e.g., ChromeDriver)

You can install the dependencies using pip:

```bash
pip install selenium opencv-python
```

## Usage

### 1. Import the Class

First, include the `SliderVR` class in your project.

### 2. Initialize and Use

Here is a basic example of how to use `SliderVR` within a Selenium automation script:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from slider_verification_breaking import SliderVB  

# Initialize WebDriver
driver = webdriver.Chrome()
driver.get("https://example.com/login")  # Replace with the actual URL

try:
    # Locate the background image and slider element
    # Note: Adjust the selectors based on the target website's structure
    bg_element = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, "slideBg"))
    )
    slider_element = driver.find_element(By.CSS_SELECTOR, ".slider-btn")

    # Initialize the solver
    solver = SliderVR(driver, bg_element, slider_element)

    # Start the verification process
    solver.slider_ver()

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Clean up
    driver.quit()
```

## How It Works

1.  **Image Capture**: The script takes screenshots of the slider background and the slider knob.
2.  **Gap Detection**:
    *   Converts images to grayscale.
    *   Applies Canny edge detection.
    *   Uses template matching to find where the slider fits into the background.
    *   Ignores the initial left-side area to prevent false positives.
3.  **Distance Calculation**:
    *   Calculates the scaling factor between the browser's rendered image and the actual image file.
    *   Computes the physical distance the slider needs to move on the screen.
4.  **Movement Simulation**: Generates a trajectory that mimics human behavior (accelerating start, decelerating end) and performs the drag-and-drop action.

## Customization

*   **`min_x` parameter**: In `calculate_distance`, you can adjust `min_x` (default 60) to change the width of the ignored area on the left side of the image. This is useful if the initial slider position interferes with detection.
*   **Movement Track**: You can modify `get_track` to change the velocity and acceleration profiles of the mouse movement.

## Disclaimer

This tool is for educational and testing purposes only. Please ensure you comply with the terms of service of the websites you test against.
