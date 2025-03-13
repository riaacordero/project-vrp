# Vehicle Routing Prediction Model

This project implements a vehicle routing prediction model to visualize the most efficient delivery route using customer delivery data and the Open Route Service (ORS) API.

## Project Structure

- `src/`: Contains the main application code.
  - `main.py`: Entry point of the application.
  - `data/`: Contains the delivery data CSV file.
  - `models/`: Contains the route optimization logic.
  - `utils/`: Contains utility functions and classes for data loading, API communication, and map visualization.
  - `templates/`: Contains HTML templates for displaying the route map.
- `tests/`: Contains unit tests for the route optimization logic.
- `requirements.txt`: Lists the project dependencies.
- `config.py`: Contains configuration constants.
- `README.md`: Documentation for the project.

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd delivery-route-optimizer
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python src/main.py
   ```

## Usage

The application loads delivery data from the CSV file, optimizes the delivery route using the ORS API, and visualizes the route on an HTML map.

## Overview

This project aims to provide an efficient solution for delivery route optimization, helping to reduce delivery times and improve overall logistics efficiency.
