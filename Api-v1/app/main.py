from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from typing import Optional, List, Literal, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import os
import shutil
import subprocess
import uuid
from pathlib import Path
import tempfile


os.makedirs("static", exist_ok=True)
os.makedirs("../Csv-Creator/uploads", exist_ok=True)
os.makedirs("../Csv-Creator/processed", exist_ok=True)

# # Create the HTML file in the static directory
# html_content = """<!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Climate Data Time Series Interface</title>
#     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.css" />
#     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
#     <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
#     <style>
#         body, html {
#             margin: 0;
#             padding: 0;
#             height: 100%;
#             font-family: Arial, sans-serif;
#         }
#         .container {
#             display: flex;
#             flex-direction: column;
#             height: 100vh;
#         }
#         .top-section {
#             display: flex;
#             height: 60%;
#         }
#         #map {
#             flex: 2;
#             width: 100%;
#         }
#         .controls {
#             flex: 1;
#             padding: 20px;
#             background-color: #f5f5f5;
#             overflow-y: auto;
#         }
#         .chart-section {
#             height: 40%;
#             padding: 20px;
#             background-color: #fff;
#             border-top: 1px solid #ddd;
#         }
#         h3 {
#             margin-top: 0;
#             margin-bottom: 15px;
#             color: #333;
#         }
#         label {
#             display: block;
#             margin-bottom: 5px;
#             font-weight: bold;
#         }
#         select, input {
#             width: 100%;
#             padding: 8px;
#             margin-bottom: 15px;
#             border: 1px solid #ddd;
#             border-radius: 4px;
#         }
#         button {
#             padding: 10px 15px;
#             margin-bottom: 10px;
#             background-color: #4CAF50;
#             color: white;
#             border: none;
#             cursor: pointer;
#             border-radius: 4px;
#             width: 100%;
#         }
#         button:hover {
#             background-color: #45a049;
#         }
#         .coordinates {
#             margin-top: 15px;
#             padding: 10px;
#             background-color: #e9e9e9;
#             border-radius: 4px;
#         }
#         .loading {
#             display: none;
#             margin-top: 10px;
#             color: #666;
#         }
#         .error {
#             color: #d9534f;
#             margin-top: 10px;
#         }
#         #chartContainer {
#             width: 100%;
#             height: 100%;
#         }
#     </style>
# </head>
# <body>
#     <div class="container">
#         <div class="top-section">
#             <div id="map"></div>
#             <div class="controls">
#                 <h3>Time Series Data</h3>
                
#                 <div class="coordinates" id="selected-point">
#                     <p>Click on the map to select a point.</p>
#                 </div>
                
#                 <label for="data-source">Data Source:</label>
#                 <select id="data-source">
#                     <option value="wc">WorldClim</option>
#                     <option value="spei">SPEI</option>
#                     <option value="chirps">CHIRPS</option>
#                     <option value="et">ET</option>
#                     <option value="elev">Elevation</option>
#                     <option value="sg">SoilGrids</option>
#                     <option value="tc">TerraClim</option>
#                     <option value="np">NASA POWER</option>
#                 </select>
                
#                 <label for="variable">Variable:</label>
#                 <select id="variable">
#                     <option value="prec">Precipitation</option>
#                     <option value="tmax">Max Temperature</option>
#                     <option value="tmin">Min Temperature</option>
#                 </select>
                
#                 <div id="date-controls">
#                     <label for="start-date">Start Date:</label>
#                     <input type="date" id="start-date">
                    
#                     <label for="end-date">End Date:</label>
#                     <input type="date" id="end-date">
#                 </div>
                
#                 <button id="fetch-data">Fetch Time Series Data</button>
#                 <button id="clear-selection">Clear Selection</button>
                
#                 <div id="loading" class="loading">Loading data...</div>
#                 <div id="error" class="error"></div>
#             </div>
#         </div>
#         <div class="chart-section">
#             <div id="chartContainer">
#                 <canvas id="timeSeriesChart"></canvas>
#             </div>
#         </div>
#     </div>

#     <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.js"></script>
#     <script>
#         // Initialize map
#         const map = L.map('map').setView([0, 0], 2);
        
#         // Add OpenStreetMap tile layer
#         L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
#             attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
#         }).addTo(map);
        
#         // Define the bounding box (-94.187, -39.020, 37.062, 18.229)
#         const bboxCoords = [
#             [-39.020, -94.187], // Southwest corner (lat, lng)
#             [18.229, 37.062]    // Northeast corner (lat, lng)
#         ];
        
#         // Display the bounding box on the map
#         const bbox = L.rectangle(bboxCoords, {
#             color: "#ff7800",
#             weight: 2,
#             fillOpacity: 0.1
#         }).addTo(map);
        
#         // Fit map to the bounding box
#         map.fitBounds(bboxCoords);
        
#         // Variables to store selected point
#         let selectedPoint = null;
#         let selectedMarker = null;
#         let timeSeriesChart = null;
        
#         // Update variable dropdown based on selected data source
#         document.getElementById('data-source').addEventListener('change', function() {
#             const dataSource = this.value;
#             const variableSelect = document.getElementById('variable');
#             const dateControls = document.getElementById('date-controls');
            
#             // Clear current options
#             variableSelect.innerHTML = '';
            
#             // Add appropriate options based on data source
#             if (dataSource === 'wc') {
#                 addOption(variableSelect, 'prec', 'Precipitation');
#                 addOption(variableSelect, 'tmax', 'Max Temperature');
#                 addOption(variableSelect, 'tmin', 'Min Temperature');
#                 dateControls.style.display = 'block';
#             } else if (dataSource === 'spei') {
#                 addOption(variableSelect, 'spei', 'SPEI');
#                 dateControls.style.display = 'block';
#             } else if (dataSource === 'chirps') {
#                 addOption(variableSelect, 'chirps', 'Precipitation');
#                 dateControls.style.display = 'block';
#             } else if (dataSource === 'et') {
#                 addOption(variableSelect, 'et', 'Evapotranspiration');
#                 dateControls.style.display = 'block';
#             } else if (dataSource === 'elev') {
#                 addOption(variableSelect, 'elev', 'Elevation');
#                 dateControls.style.display = 'none';
#             } else if (dataSource === 'sg') {
#                 addOption(variableSelect, 'bdod', 'Bulk Density');
#                 addOption(variableSelect, 'cec', 'Cation Exchange Capacity');
#                 addOption(variableSelect, 'cfvo', 'Coarse Fragments Volumetric');
#                 addOption(variableSelect, 'clay', 'Clay Content');
#                 addOption(variableSelect, 'nitrogen', 'Nitrogen');
#                 addOption(variableSelect, 'ocd', 'Organic Carbon Density');
#                 addOption(variableSelect, 'ocs', 'Organic Carbon Stock');
#                 addOption(variableSelect, 'phh2o', 'pH in H2O');
#                 addOption(variableSelect, 'sand', 'Sand Content');
#                 addOption(variableSelect, 'silt', 'Silt Content');
#                 addOption(variableSelect, 'soc', 'Soil Organic Carbon');
#                 addOption(variableSelect, 'wv0010', 'Water Vapor Content at 10cm Depth');
#                 addOption(variableSelect, 'wv0030', 'Water Vapor Content at 30cm Depth');
#                 addOption(variableSelect, 'wv1500', 'Water Vapor Content at 1500cm Depth');
#                 dateControls.style.display = 'none';
#             }else if (dataSource === 'tc') {
#                 // TerraClim variables
#                 addOption(variableSelect, 'aet', 'Actual Evapotranspiration');
#                 addOption(variableSelect, 'def', 'Water Deficit');
#                 addOption(variableSelect, 'pdsi', 'PDSI');
#                 addOption(variableSelect, 'pet', 'Potential Evapotranspiration');
#                 addOption(variableSelect, 'ppt', 'Precipitation');
#                 addOption(variableSelect, 'q', 'Runoff');
#                 addOption(variableSelect, 'soil', 'Soil Moisture');
#                 addOption(variableSelect, 'srad', 'Solar Radiation');
#                 addOption(variableSelect, 'tmax', 'Max Temperature');
#                 addOption(variableSelect, 'tmin', 'Min Temperature');
#                 addOption(variableSelect, 'vap', 'Vapor Pressure');
#                 addOption(variableSelect, 'vpd', 'Vapor Pressure Deficit');
#                 addOption(variableSelect, 'ws', 'Wind Speed');
#                 dateControls.style.display = 'block';
#             } else if (dataSource === 'np') {
#                 // NASA POWER variables
#                 addOption(variableSelect, 'airmass', 'Air Mass');
#                 addOption(variableSelect, 'allsky_kt', 'All-Sky Kt');
#                 addOption(variableSelect, 'allsky_nkt', 'All-Sky NKt');
#                 addOption(variableSelect, 'allsky_sfc_lw_dwn', 'All-Sky Surface LW Down');
#                 addOption(variableSelect, 'allsky_sfc_lw_up', 'All-Sky Surface LW Up');
#                 addOption(variableSelect, 'allsky_sfc_par_diff', 'All-Sky Surface PAR Diffuse');
#                 addOption(variableSelect, 'allsky_sfc_par_dirh', 'All-Sky Surface PAR Direct Horizontal');
#                 addOption(variableSelect, 'allsky_sfc_par_tot', 'All-Sky Surface PAR Total');
#                 addOption(variableSelect, 'allsky_sfc_sw_diff', 'All-Sky Surface SW Diffuse');
#                 addOption(variableSelect, 'allsky_sfc_sw_dirh', 'All-Sky Surface SW Direct Horizontal');
#                 addOption(variableSelect, 'allsky_sfc_sw_dni', 'All-Sky Surface SW DNI');
#                 addOption(variableSelect, 'allsky_sfc_sw_dwn', 'All-Sky Surface SW Down');
#                 addOption(variableSelect, 'allsky_sfc_sw_up', 'All-Sky Surface SW Up');
#                 addOption(variableSelect, 'allsky_sfc_uv_index', 'All-Sky Surface UV Index');
#                 addOption(variableSelect, 'allsky_sfc_uva', 'All-Sky Surface UVA');
#                 addOption(variableSelect, 'allsky_sfc_uvb', 'All-Sky Surface UVB');
#                 addOption(variableSelect, 'allsky_srf_alb', 'All-Sky Surface Albedo');
#                 addOption(variableSelect, 'aod_55', 'AOD 550nm');
#                 addOption(variableSelect, 'aod_55_adj', 'AOD 550nm Adjusted');
#                 addOption(variableSelect, 'aod_84', 'AOD 840nm');
#                 addOption(variableSelect, 'cloud_amt', 'Cloud Amount');
#                 addOption(variableSelect, 'cloud_amt_day', 'Cloud Amount Day');
#                 addOption(variableSelect, 'cloud_amt_night', 'Cloud Amount Night');
#                 addOption(variableSelect, 'cloud_od', 'Cloud Optical Depth');
#                 addOption(variableSelect, 'clrsky_days', 'Clear Sky Days');
#                 addOption(variableSelect, 'clrsky_kt', 'Clear Sky Kt');
#                 addOption(variableSelect, 'clrsky_nkt', 'Clear Sky NKt');
#                 addOption(variableSelect, 'clrsky_sfc_lw_dwn', 'Clear Sky Surface LW Down');
#                 addOption(variableSelect, 'clrsky_sfc_lw_up', 'Clear Sky Surface LW Up');
#                 addOption(variableSelect, 'clrsky_sfc_par_diff', 'Clear Sky Surface PAR Diffuse');
#                 addOption(variableSelect, 'clrsky_sfc_par_dirh', 'Clear Sky Surface PAR Direct Horizontal');
#                 addOption(variableSelect, 'clrsky_sfc_par_tot', 'Clear Sky Surface PAR Total');
#                 addOption(variableSelect, 'clrsky_sfc_sw_diff', 'Clear Sky Surface SW Diffuse');
#                 addOption(variableSelect, 'clrsky_sfc_sw_dirh', 'Clear Sky Surface SW Direct Horizontal');
#                 addOption(variableSelect, 'clrsky_sfc_sw_dni', 'Clear Sky Surface SW DNI');
#                 addOption(variableSelect, 'clrsky_sfc_sw_dwn', 'Clear Sky Surface SW Down');
#                 addOption(variableSelect, 'clrsky_sfc_sw_up', 'Clear Sky Surface SW Up');
#                 addOption(variableSelect, 'clrsky_srf_alb', 'Clear Sky Surface Albedo');
#                 addOption(variableSelect, 'midday_insol', 'Midday Insolation');
#                 addOption(variableSelect, 'original_allsky_sfc_sw_diff', 'Original All-Sky Surface SW Diffuse');
#                 addOption(variableSelect, 'original_allsky_sfc_sw_dirh', 'Original All-Sky Surface SW Direct Horizontal');
#                 addOption(variableSelect, 'psh', 'Peak Sun Hours');
#                 addOption(variableSelect, 'pw', 'Precipitable Water');
#                 addOption(variableSelect, 'srf_alb_adj', 'Surface Albedo Adjusted');
#                 addOption(variableSelect, 'toa_sw_dni', 'TOA SW DNI');
#                 addOption(variableSelect, 'toa_sw_dwn', 'TOA SW Down');
#                 addOption(variableSelect, 'ts_adj', 'Temperature Adjusted');
#                 dateControls.style.display = 'block';
#             }
#     });
        
#         // Handle map click event
#         map.on('click', function(e) {
#             const lat = e.latlng.lat.toFixed(6);
#             const lon = e.latlng.lng.toFixed(6);
            
#             // Update selected point
#             selectedPoint = { lat, lon };
            
#             // Update UI
#             document.getElementById('selected-point').innerHTML = `
#                 <strong>Selected Point:</strong><br>
#                 Latitude: ${lat}<br>
#                 Longitude: ${lon}
#             `;
            
#             // Remove previous marker if exists
#             if (selectedMarker) {
#                 map.removeLayer(selectedMarker);
#             }
            
#             // Add new marker
#             selectedMarker = L.marker([lat, lon]).addTo(map);
#         });
        
        
#         // Function to display static data (for Elevation and SoilGrids)
#         function displayStaticData(data, dataSource, variable) {
#             // Debug: Log the data to see what's being received
#             console.log("Static data received:", data);
            
#             // Create a context for the chart
#             const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            
#             // Destroy previous chart if exists
#             if (timeSeriesChart) {
#                 timeSeriesChart.destroy();
#             }
            
#             // Check if data has the expected structure
#             if (!data.hasOwnProperty('value')) {
#                 // Try to access the value through a different property or structure
#                 let value = null;
#                 if (data.values && data.values.length > 0) {
#                     value = data.values[0].value;
#                 } else if (typeof data === 'object') {
#                     // Try to find the first numeric value
#                     for (let key in data) {
#                         if (!isNaN(data[key])) {
#                             value = data[key];
#                             break;
#                         }
#                     }
#                 }
                
#                 if (value === null) {
#                     showError(`Could not extract value from the response for ${dataSource}.`);
#                     return;
#                 }
                
#                 // Use the extracted value
#                 data = { value: value, lat: selectedPoint.lat, lon: selectedPoint.lon };
#             }
            
#             // For static data, we'll create a simple bar chart showing the value
#             timeSeriesChart = new Chart(ctx, {
#                 type: 'bar',
#                 data: {
#                     labels: [getVariableLabel(variable, dataSource)],
#                     datasets: [{
#                         label: getVariableLabel(variable, dataSource),
#                         data: [data.value],
#                         backgroundColor: getChartColor(variable, 0.6),
#                         borderColor: getChartColor(variable),
#                         borderWidth: 1
#                     }]
#                 },
#                 options: {
#                     responsive: true,
#                     maintainAspectRatio: false,
#                     scales: {
#                         y: {
#                             beginAtZero: false,
#                             title: {
#                                 display: true,
#                                 text: getUnitLabel(variable, dataSource)
#                             }
#                         }
#                     },
#                     plugins: {
#                         title: {
#                             display: true,
#                             text: `${getVariableLabel(variable, dataSource)} at Lat: ${data.lat}, Lon: ${data.lon}`
#                         },
#                         legend: {
#                             display: false
#                         },
#                         tooltip: {
#                             callbacks: {
#                                 label: function(context) {
#                                     return `${context.dataset.label}: ${context.raw} ${getUnitLabel(variable, dataSource)}`;
#                                 }
#                             }
#                         }
#                     }
#                 }
#             });
#         }
        
#         // Fetch time series data button click handler
#         document.getElementById('fetch-data').addEventListener('click', async function() {
#             // Check if a point is selected
#             if (!selectedPoint) {
#                 showError('Please select a point on the map first.');
#                 return;
#             }
            
#             // Get form values
#             const dataSource = document.getElementById('data-source').value;
#             const variable = document.getElementById('variable').value;
            
#             // Build API URL base
#             let apiUrl = '';
        
#             if (dataSource === 'elev' || dataSource === 'sg') {
#                 // For static data sources
#                 apiUrl = `/climate-data-timeseries/?lat=${selectedPoint.lat}&lon=${selectedPoint.lon}&data_source=${dataSource}&variable=${variable}`;
                
#                 // For SoilGrids, we don't need dates
#                 if (dataSource === 'sg') {
#                     apiUrl += '&year=2023&month=1'; // Dummy date as required by API
#                 }
#             } else {
#                 // For time series data
#                 const startDate = document.getElementById('start-date').value;
#                 const endDate = document.getElementById('end-date').value;
                
#                 // Validate dates
#                 if (!startDate || !endDate) {
#                     showError('Please select start and end dates.');
#                     return;
#                 }
                
#                 apiUrl = `/climate-data-timeseries/?lat=${selectedPoint.lat}&lon=${selectedPoint.lon}&start_date=${startDate}&end_date=${endDate}&data_source=${dataSource}&variable=${variable}`;
#             }
            
#             // Show loading
#             document.getElementById('loading').style.display = 'block';
#             document.getElementById('error').textContent = '';
            
#             try {
#                 // Fetch data
#                 const response = await fetch(apiUrl);
                
#                 if (!response.ok) {
#                     const errorData = await response.json();
#                     throw new Error(errorData.detail || 'Failed to fetch data');
#                 }
                
#                 const data = await response.json();
                
#                 // Process and display the data
#                 if (dataSource === 'elev' || dataSource === 'sg') {
#                     displayStaticData(data, dataSource, variable);
#                 } else {
#                     displayTimeSeriesData(data);
#                 }
#             } catch (error) {
#                 showError(error.message);
#             } finally {
#                 // Hide loading
#                 document.getElementById('loading').style.display = 'none';
#             }
#         });
        
#         // Clear selection button click handler
#         document.getElementById('clear-selection').addEventListener('click', function() {
#             // Clear selected point
#             selectedPoint = null;
            
#             // Remove marker if exists
#             if (selectedMarker) {
#                 map.removeLayer(selectedMarker);
#                 selectedMarker = null;
#             }
            
#             // Reset UI
#             document.getElementById('selected-point').innerHTML = '<p>Click on the map to select a point.</p>';
            
#             // Clear chart
#             if (timeSeriesChart) {
#                 timeSeriesChart.destroy();
#                 timeSeriesChart = null;
#             }
#         });
        
#         // Function to display time series data
#         function displayTimeSeriesData(data) {
#             // Prepare chart data
#             const chartLabels = [];
#             const chartData = [];
            
#             // Process values based on cadence
#             data.values.forEach(entry => {
#                 if (entry.value !== null) {
#                     // Format date label based on cadence
#                     let dateLabel;
#                     if (data.cadence === 'monthly') {
#                         dateLabel = `${entry.year}-${entry.month.toString().padStart(2, '0')}`;
#                     } else {
#                         dateLabel = entry.date;
#                     }
                    
#                     chartLabels.push(dateLabel);
#                     chartData.push(entry.value);
#                 }
#             });
            
#             // Create chart
#             const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            
#             // Destroy previous chart if exists
#             if (timeSeriesChart) {
#                 timeSeriesChart.destroy();
#             }
            
#             // Create new chart
#             timeSeriesChart = new Chart(ctx, {
#                 type: 'line',
#                 data: {
#                     labels: chartLabels,
#                     datasets: [{
#                         label: getVariableLabel(data.variable, data.data_source),
#                         data: chartData,
#                         borderColor: getChartColor(data.variable),
#                         backgroundColor: getChartColor(data.variable, 0.1),
#                         tension: 0.1,
#                         pointRadius: 3,
#                         pointHoverRadius: 5
#                     }]
#                 },
#                 options: {
#                     responsive: true,
#                     maintainAspectRatio: false,
#                     scales: {
#                         y: {
#                             beginAtZero: false,
#                             title: {
#                                 display: true,
#                                 text: getUnitLabel(data.variable, data.data_source)
#                             }
#                         },
#                         x: {
#                             title: {
#                                 display: true,
#                                 text: getCadenceLabel(data.cadence)
#                             }
#                         }
#                     },
#                     plugins: {
#                         title: {
#                             display: true,
#                             text: `${getVariableLabel(data.variable, data.data_source)} at Lat: ${data.lat}, Lon: ${data.lon}`
#                         },
#                         legend: {
#                             display: true
#                         },
#                         tooltip: {
#                             callbacks: {
#                                 label: function(context) {
#                                     return `${context.dataset.label}: ${context.raw} ${getUnitLabel(data.variable, data.data_source)}`;
#                                 }
#                             }
#                         }
#                     }
#                 }
#             });
#         }
        
#         // Function to display static data (for Elevation and SoilGrids)
#         function displayStaticData(data, dataSource, variable) {
#             // Create a context for the chart
#             const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            
#             // Destroy previous chart if exists
#             if (timeSeriesChart) {
#                 timeSeriesChart.destroy();
#             }
#             // For static data, we'll create a simple bar chart showing the value
#             timeSeriesChart = new Chart(ctx, {
#                 type: 'bar',
#                 data: {
#                     labels: [getVariableLabel(variable, dataSource)],
#                     datasets: [{
#                         label: getVariableLabel(variable, dataSource),
#                         data: [data.values[0].value],
#                         backgroundColor: getChartColor(variable, 0.6),
#                         borderColor: getChartColor(variable),
#                         borderWidth: 1
#                     }]
#                 },
#                 options: {
#                     responsive: true,
#                     maintainAspectRatio: false,
#                     scales: {
#                         y: {
#                             beginAtZero: false,
#                             title: {
#                                 display: true,
#                                 text: getUnitLabel(variable, dataSource)
#                             }
#                         }
#                     },
#                     plugins: {
#                         title: {
#                             display: true,
#                             text: `${getVariableLabel(variable, dataSource)} at Lat: ${data.lat}, Lon: ${data.lon}`
#                         },
#                         legend: {
#                             display: false
#                         },
#                         tooltip: {
#                             callbacks: {
#                                 label: function(context) {
#                                     return `${context.dataset.label}: ${context.raw} ${getUnitLabel(variable, dataSource)}`;
#                                 }
#                             }
#                         }
#                     }
#                 }
#             });
#         }
        
#         // Helper functions
#         function addOption(select, value, text) {
#             const option = document.createElement('option');
#             option.value = value;
#             option.textContent = text;
#             select.appendChild(option);
#         }
        
#         function showError(message) {
#             document.getElementById('error').textContent = message;
#             document.getElementById('loading').style.display = 'none';
#         }
        
#         function getChartColor(variable, alpha = 1) {
#             const colors = {
#                 'prec': `rgba(0, 119, 190, ${alpha})`,
#                 'chirps': `rgba(0, 119, 190, ${alpha})`,
#                 'tmax': `rgba(255, 69, 0, ${alpha})`,
#                 'tmin': `rgba(30, 144, 255, ${alpha})`,
#                 'spei': `rgba(50, 205, 50, ${alpha})`,
#                 'et': `rgba(128, 0, 128, ${alpha})`,
#                 'elev': `rgba(139, 69, 19, ${alpha})`,
#                 'bdod': `rgba(165, 42, 42, ${alpha})`,
#                 'cec': `rgba(255, 140, 0, ${alpha})`,
#                 'cfvo': `rgba(128, 128, 0, ${alpha})`,
#                 'clay': `rgba(210, 180, 140, ${alpha})`,
#                 'nitrogen': `rgba(0, 128, 0, ${alpha})`,
#                 'ocd': `rgba(0, 0, 139, ${alpha})`,
#                 'ocs': `rgba(72, 61, 139, ${alpha})`,
#                 'phh2o': `rgba(186, 85, 211, ${alpha})`,
#                 'sand': `rgba(240, 230, 140, ${alpha})`,
#                 'silt': `rgba(189, 183, 107, ${alpha})`,
#                 'soc': `rgba(85, 107, 47, ${alpha})`
#             };
            
#             return colors[variable] || `rgba(100, 100, 100, ${alpha})`;
#         }
        
#         function getVariableLabel(variable, dataSource) {
#             const labels = {
#                 'prec': 'Precipitation',
#                 'chirps': 'Precipitation',
#                 'tmax': 'Maximum Temperature',
#                 'tmin': 'Minimum Temperature',
#                 'spei': 'SPEI',
#                 'et': 'Evapotranspiration',
#                 'elev': 'Elevation',
#                 'bdod': 'Bulk Density',
#                 'cec': 'Cation Exchange Capacity',
#                 'cfvo': 'Coarse Fragments Volumetric',
#                 'clay': 'Clay Content',
#                 'nitrogen': 'Nitrogen',
#                 'ocd': 'Organic Carbon Density',
#                 'ocs': 'Organic Carbon Stock',
#                 'phh2o': 'pH in H2O',
#                 'sand': 'Sand Content',
#                 'silt': 'Silt Content',
#                 'soc': 'Soil Organic Carbon',
#                 // TerraClim variables
#                 'aet': 'Actual Evapotranspiration',
#                 'def': 'Water Deficit',
#                 'pdsi': 'Palmer Drought Severity Index',
#                 'pet': 'Potential Evapotranspiration',
#                 'ppt': 'Precipitation',
#                 'q': 'Runoff',
#                 'soil': 'Soil Moisture',
#                 'srad': 'Solar Radiation',
#                 'vap': 'Vapor Pressure',
#                 'vpd': 'Vapor Pressure Deficit',
#                 'ws': 'Wind Speed',
                
#                 // NASA POWER variables
#                 'airmass': 'Air Mass',
#                 'allsky_kt': 'All-Sky Kt',
#                 'allsky_nkt': 'All-Sky NKt',
#                 'allsky_sfc_lw_dwn': 'All-Sky Surface LW Down',
#                 'allsky_sfc_lw_up': 'All-Sky Surface LW Up',
#                 'allsky_sfc_par_diff': 'All-Sky Surface PAR Diffuse',
#                 'allsky_sfc_par_dirh': 'All-Sky Surface PAR Direct Horizontal',
#                 'allsky_sfc_par_tot': 'All-Sky Surface PAR Total',
#                 'allsky_sfc_sw_diff': 'All-Sky Surface SW Diffuse',
#                 'allsky_sfc_sw_dirh': 'All-Sky Surface SW Direct Horizontal',
#                 'allsky_sfc_sw_dni': 'All-Sky Surface SW DNI',
#                 'allsky_sfc_sw_dwn': 'All-Sky Surface SW Down',
#                 'allsky_sfc_sw_up': 'All-Sky Surface SW Up',
#                 'allsky_sfc_uv_index': 'All-Sky Surface UV Index',
#                 'allsky_sfc_uva': 'All-Sky Surface UVA',
#                 'allsky_sfc_uvb': 'All-Sky Surface UVB',
#                 'allsky_srf_alb': 'All-Sky Surface Albedo',
#                 'aod_55': 'AOD 550nm',
#                 'aod_55_adj': 'AOD 550nm Adjusted',
#                 'aod_84': 'AOD 840nm',
#                 'cloud_amt': 'Cloud Amount',
#                 'cloud_amt_day': 'Cloud Amount Day',
#                 'cloud_amt_night': 'Cloud Amount Night',
#                 'cloud_od': 'Cloud Optical Depth',
#                 'clrsky_days': 'Clear Sky Days',
#                 'clrsky_kt': 'Clear Sky Kt',
#                 'clrsky_nkt': 'Clear Sky NKt',
#                 'clrsky_sfc_lw_dwn': 'Clear Sky Surface LW Down',
#                 'clrsky_sfc_lw_up': 'Clear Sky Surface LW Up',
#                 'clrsky_sfc_par_diff': 'Clear Sky Surface PAR Diffuse',
#                 'clrsky_sfc_par_dirh': 'Clear Sky Surface PAR Direct Horizontal',
#                 'clrsky_sfc_par_tot': 'Clear Sky Surface PAR Total',
#                 'clrsky_sfc_sw_diff': 'Clear Sky Surface SW Diffuse',
#                 'clrsky_sfc_sw_dirh': 'Clear Sky Surface SW Direct Horizontal',
#                 'clrsky_sfc_sw_dni': 'Clear Sky Surface SW DNI',
#                 'clrsky_sfc_sw_dwn': 'Clear Sky Surface SW Down',
#                 'clrsky_sfc_sw_up': 'Clear Sky Surface SW Up',
#                 'clrsky_srf_alb': 'Clear Sky Surface Albedo',
#                 'midday_insol': 'Midday Insolation',
#                 'original_allsky_sfc_sw_diff': 'Original All-Sky Surface SW Diffuse',
#                 'original_allsky_sfc_sw_dirh': 'Original All-Sky Surface SW Direct Horizontal',
#                 'psh': 'Peak Sun Hours',
#                 'pw': 'Precipitable Water',
#                 'srf_alb_adj': 'Surface Albedo Adjusted',
#                 'toa_sw_dni': 'TOA SW DNI',
#                 'toa_sw_dwn': 'TOA SW Down',
#                 'ts_adj': 'Temperature Adjusted', 
#             };
            
#             return labels[variable] || variable;
#         }
        
#         function getUnitLabel(variable, dataSource) {
#             if (variable === 'prec' || variable === 'chirps' || variable === 'et') {
#                 return 'mm';
#             } else if (variable === 'tmax' || variable === 'tmin') {
#                 return '°C';
#             } else if (variable === 'spei') {
#                 return 'Index';
#             } else if (variable === 'elev') {
#                 return 'm';
#             } else if (variable === 'bdod') {
#                 return 'kg/dm³';
#             } else if (variable === 'cec') {
#                 return 'cmolc/kg';
#             } else if (variable === 'cfvo') {
#                 return '%';
#             } else if (variable === 'clay' || variable === 'sand' || variable === 'silt') {
#                 return '%';
#             } else if (variable === 'nitrogen') {
#                 return 'g/kg';
#             } else if (variable === 'ocd') {
#                 return 'kg/dm³';
#             } else if (variable === 'ocs') {
#                 return 't/ha';
#             } else if (variable === 'phh2o') {
#                 return 'pH';
#             } else if (variable === 'soc') {
#                 return 'g/kg';
#             }
#             else if (variable === 'wv0010' || variable === 'wv0030' || variable === 'wv1500') {
#                 return '';
#             }
#             //Add units for terraclim and NASA Power
#         }
        
#         function getCadenceLabel(cadence) {
#             const labels = {
#                 'daily': 'Date',
#                 '8day': 'Date',
#                 'monthly': 'Month',
#                 'aggregated': 'Data Point',
#                 'static': 'Data Point'
#             };
            
#             return labels[cadence] || 'Date';
#         }
        
#         // Set default dates (last 6 months)
#         function setDefaultDates() {
#             const today = new Date();
#             const sixMonthsAgo = new Date();
#             sixMonthsAgo.setMonth(today.getMonth() - 6);
            
#             document.getElementById('end-date').value = formatDate(today);
#             document.getElementById('start-date').value = formatDate(sixMonthsAgo);
#         }
        
#         function formatDate(date) {
#             const year = date.getFullYear();
#             const month = String(date.getMonth() + 1).padStart(2, '0');
#             const day = String(date.getDate()).padStart(2, '0');
            
#             return `${year}-${month}-${day}`;
#         }
        
#         // Initialize default dates
#         setDefaultDates();
#     </script>
# </body>
# </html>
# """

# Update DataSource and Variable Enums
class DataSource(str, Enum):
    WORLDCLIM = "wc"
    SPEI = "spei"
    CHIRPS = "chirps"
    ET = "et"
    ELEVATION = "elev"
    SOILGRIDS = "sg"
    TERRACLIM = "tc"    # Added TerraClim
    NASAPOWER = "np"    # Added NASA POWER

class Variable(str, Enum):
    # Weather and Climate variables
    CHIRPS = "chirps"
    PRECIPITATION = "prec"
    TMAX = "tmax"
    TMIN = "tmin"
    SPEI = "spei"
    ET = "et"
    
    # SoilGrids variables
    ELEVATION = "elev"  # Elevation
    BDOD = "bdod"       # Bulk density
    CEC = "cec"         # Cation exchange capacity
    CFVO = "cfvo"       # Coarse fragments volumetric
    CLAY = "clay"       # Clay content
    NITROGEN = "nitrogen" # Nitrogen
    OCD = "ocd"         # Organic carbon density
    OCS = "ocs"         # Organic carbon stock
    PHH2O = "phh2o"     # pH in H2O
    SAND = "sand"       # Sand content
    SILT = "silt"       # Silt content
    SOC = "soc"         # Soil organic carbon
    WV0010 = "wv0010"   # Water vapor content at 10cm depth
    WV0030 = "wv0030"   # Water vapor content at 30cm depth
    WV1500 = "wv1500"   # Water vapor content at 1500cm depth
    
    # TerraClim variables
    AET = "aet"         # Actual Evapotranspiration
    DEF = "def"         # Water Deficit
    PDSI = "pdsi"       # Palmer Drought Severity Index
    PET = "pet"         # Potential Evapotranspiration
    PPT = "ppt"         # Precipitation
    Q = "q"             # Runoff
    SOIL = "soil"       # Soil Moisture
    SRAD = "srad"       # Solar Radiation
    VAP = "vap"         # Vapor Pressure
    VPD = "vpd"         # Vapor Pressure Deficit
    WS = "ws"           # Wind Speed
    
    # NASA POWER variables
    AIRMASS = "airmass"
    ALLSKY_KT = "allsky_kt"
    ALLSKY_NKT = "allsky_nkt"
    ALLSKY_SFC_LW_DWN = "allsky_sfc_lw_dwn"
    ALLSKY_SFC_LW_UP = "allsky_sfc_lw_up"
    ALLSKY_SFC_PAR_DIFF = "allsky_sfc_par_diff"
    ALLSKY_SFC_PAR_DIRH = "allsky_sfc_par_dirh"
    ALLSKY_SFC_PAR_TOT = "allsky_sfc_par_tot"
    ALLSKY_SFC_SW_DIFF = "allsky_sfc_sw_diff"
    ALLSKY_SFC_SW_DIRH = "allsky_sfc_sw_dirh"
    ALLSKY_SFC_SW_DNI = "allsky_sfc_sw_dni"
    ALLSKY_SFC_SW_DWN = "allsky_sfc_sw_dwn"
    ALLSKY_SFC_SW_UP = "allsky_sfc_sw_up"
    ALLSKY_SFC_UV_INDEX = "allsky_sfc_uv_index"
    ALLSKY_SFC_UVA = "allsky_sfc_uva"
    ALLSKY_SFC_UVB = "allsky_sfc_uvb"
    ALLSKY_SRF_ALB = "allsky_srf_alb"
    AOD_55 = "aod_55"
    AOD_55_ADJ = "aod_55_adj"
    AOD_84 = "aod_84"
    CLOUD_AMT = "cloud_amt"
    CLOUD_AMT_DAY = "cloud_amt_day"
    CLOUD_AMT_NIGHT = "cloud_amt_night"
    CLOUD_OD = "cloud_od"
    CLRSKY_DAYS = "clrsky_days"
    CLRSKY_KT = "clrsky_kt"
    CLRSKY_NKT = "clrsky_nkt"
    CLRSKY_SFC_LW_DWN = "clrsky_sfc_lw_dwn"
    CLRSKY_SFC_LW_UP = "clrsky_sfc_lw_up"
    CLRSKY_SFC_PAR_DIFF = "clrsky_sfc_par_diff"
    CLRSKY_SFC_PAR_DIRH = "clrsky_sfc_par_dirh"
    CLRSKY_SFC_PAR_TOT = "clrsky_sfc_par_tot"
    CLRSKY_SFC_SW_DIFF = "clrsky_sfc_sw_diff"
    CLRSKY_SFC_SW_DIRH = "clrsky_sfc_sw_dirh"
    CLRSKY_SFC_SW_DNI = "clrsky_sfc_sw_dni"
    CLRSKY_SFC_SW_DWN = "clrsky_sfc_sw_dwn"
    CLRSKY_SFC_SW_UP = "clrsky_sfc_sw_up"
    CLRSKY_SRF_ALB = "clrsky_srf_alb"
    MIDDAY_INSOL = "midday_insol"
    ORIGINAL_ALLSKY_SFC_SW_DIFF = "original_allsky_sfc_sw_diff"
    ORIGINAL_ALLSKY_SFC_SW_DIRH = "original_allsky_sfc_sw_dirh"
    PSH = "psh"
    PW = "pw"
    SRF_ALB_ADJ = "srf_alb_adj"
    TOA_SW_DNI = "toa_sw_dni"
    TOA_SW_DWN = "toa_sw_dwn"
    TS_ADJ = "ts_adj"

class Cadence(str, Enum):
    DAILY = "daily"         # For CHIRPS
    EIGHT_DAY = "8day"      # For ET
    MONTHLY = "monthly"     # For WorldClim, SPEI
    STATIC = "static"       # For Elevation
    AGGREGATED = "aggregated" # For SoilGrids

app = FastAPI(title="Camcore Database API")



def get_table_name(data_source: DataSource, variable: Variable, year: Optional[int] = None, 
                  month: Optional[int] = None, day: Optional[int] = None):
    if data_source == DataSource.WORLDCLIM:
        return f"{data_source.value}_{variable.value}_{year}_{month:02d}"
    
    elif data_source == DataSource.SPEI:
        return f"{data_source.value}_{year}_{month:02d}"
    
    elif data_source == DataSource.CHIRPS:
        if day is None:
            raise ValueError("Day is required for CHIRPS data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    
    elif data_source == DataSource.ET:
        if day is None:
            raise ValueError("Day is required for ET data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    elif data_source == DataSource.ELEVATION:
        return "elev"
    elif data_source == DataSource.SOILGRIDS:
        return f"sg_{variable.value}"
    elif data_source == DataSource.TERRACLIM:
        return f"terraclim_{variable.value}_{year}_{month:02d}"
    elif data_source == DataSource.NASAPOWER:
        return f"np_{variable.value}_{year}_{month:02d}"    
    else:
        raise ValueError(f"Unknown data source: {data_source}")

def get_cadence_for_data_source(data_source: DataSource):
    if data_source == DataSource.WORLDCLIM or data_source == DataSource.SPEI or data_source == DataSource.TERRACLIM or data_source == DataSource.NASAPOWER:
        return Cadence.MONTHLY
    elif data_source == DataSource.CHIRPS:
        return Cadence.DAILY
    elif data_source == DataSource.ET:
        return Cadence.EIGHT_DAY
    elif data_source == DataSource.ELEVATION:
        return Cadence.STATIC
    elif data_source == DataSource.SOILGRIDS:
        return Cadence.AGGREGATED
    
    else:
        raise ValueError(f"Unknown data source: {data_source}")

def validate_date_params(data_source: DataSource, year: int, month: int, day: Optional[int] = None):
    cadence = get_cadence_for_data_source(data_source)
    
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    if cadence == Cadence.DAILY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for CHIRPS data source")
        days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  
        if not (1 <= day <= days_in_month[month]):
            raise HTTPException(status_code=400, detail=f"Day must be between 1 and {days_in_month[month]} for month {month}")
    
    elif cadence == Cadence.EIGHT_DAY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for ET data source")
        
        try:
            check_date = datetime(year, month, day)
            baseline = datetime(2000, 1, 1)
            
            if check_date < baseline:
                raise HTTPException(
                    status_code=400, 
                    detail=f"ET data is only available from 2000-01-01 onwards."
                )
            
            days_diff = (check_date - baseline).days
            if days_diff % 8 != 0:
                days_to_next = 8 - (days_diff % 8)
                next_valid_date = check_date + timedelta(days=days_to_next)
                
                days_to_prev = days_diff % 8
                prev_valid_date = check_date - timedelta(days=days_to_prev)
                
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid ET date. ET data is available every 8 days starting from 2000-01-01. " + 
                        f"The nearest valid dates are {prev_valid_date.strftime('%Y-%m-%d')} and {next_valid_date.strftime('%Y-%m-%d')}."
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date")
        
def get_variable_param(
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et, elev, sg)")
) -> Optional[Variable]:
    """Dependency that only requests variable parameter if data_source is WorldClim"""
    if data_source == DataSource.WORLDCLIM:
        return Query(None, description="Climate variable (prec, tmax, tmin)")
    if data_source == DataSource.NASAPOWER:
        return Query(None, description="NASA POWER variable (airmass, allsky_kt, etc.)")
    if data_source == DataSource.TERRACLIM:
        return Query(None, description="TerraClim variable (aet, def, pdsi, etc.)")
    return None
       
def is_valid_et_date(date_obj: datetime) -> bool:
    """Check if a date is a valid ET date (follows the 8-day cadence from 2000-01-01)"""
    start_date = datetime(2000, 1, 1)
    
    if date_obj < start_date:
        return False
    
    days_diff = (date_obj - start_date).days
    
    return days_diff % 8 == 0

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Camcore Database API",
        "available_data_sources": {
            "wc": "WorldClim (monthly: precipitation, tmax, tmin)",
            "spei": "SPEI (monthly)",
            "chirps": "CHIRPS (daily precipitation)",
            "et": "Evapotranspiration (8-day cadence)",
            "elev": "Elevation (static)",
            "sg": "SoilGrids (static soil properties)",
            "tc": "TerraClim (monthly climate data)",
            "np": "NASA POWER (monthly climate and solar data)"
        }
    }

@app.get("/available-data/")
async def get_available_data():
    return {
        "data_sources": {
            "wc": {
                "description": "WorldClim - Monthly climate data",
                "variables": ["prec", "tmax", "tmin"],
                "cadence": "monthly",
                "unit": ["mm", "°C", "°C"]
            },
            "spei": {
                "description": "Standardized Precipitation Evapotranspiration Index",
                "variables": ["spei"],
                "cadence": "monthly",
                "unit": "no unit"
            },
            "chirps": {
                "description": "Climate Hazards Group InfraRed Precipitation with Station data",
                "variables": ["prec"],
                "cadence": "daily",
                "unit": "mm"
            },
            "et": {
                "description": "Evapotranspiration data",
                "variables": ["et"],
                "cadence": "8day",
                "unit": "mm"
            },
            "elev": {
                "description": "Elevation data",
                "variables": ["elev"],
                "cadence": "static",
                "unit": "m"
            },
            "sg": {
                "description": "SoilGrids - Soil properties",
                "variables": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
                "cadence": "static",
                "unit": "various"
            },
            "tc": {
                "description": "TerraClim - Monthly climate data",
                "variables": ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmax", "tmin", "vap", "vpd", "ws"],
                "cadence": "monthly",
                "unit": ["mm", "mm", "mm", "mm", "mm", "mm", "W/m2", "mm", "C", "C", "kPa", "m/s", "kPa", "unitless"]
            },
            "np": {
                "description": "NASA POWER - Monthly climate and solar radiation data",
                "variables": ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff", 
                             "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", 
                             "allsky_sfc_sw_dni", "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", 
                             "allsky_sfc_uva", "allsky_sfc_uvb", "allsky_srf_alb", "aod_55", "aod_55_adj", "aod_84", 
                             "cloud_amt", "cloud_amt_day", "cloud_amt_night", "cloud_od", "clrsky_days", "clrsky_kt", 
                             "clrsky_nkt", "clrsky_sfc_lw_dwn", "clrsky_sfc_lw_up", "clrsky_sfc_par_diff", "clrsky_sfc_par_dirh", 
                             "clrsky_sfc_par_tot", "clrsky_sfc_sw_diff", "clrsky_sfc_sw_dirh", "clrsky_sfc_sw_dni", 
                             "clrsky_sfc_sw_dwn", "clrsky_sfc_sw_up", "clrsky_srf_alb", "midday_insol", 
                             "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw", "srf_alb_adj", 
                             "toa_sw_dni", "toa_sw_dwn", "ts_adj"],
                "cadence": "monthly",
                "unit": ["dimensionless", "dimensionless", "dimensionless", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2 x 40", "dimensionless", "dimensionless", "dimensionless", "dimensionless", "%", "%", "%", "dimensionless", "Days", "dimensionless", "dimensionless", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "dimensionless", "W m-2", "W m-2", "cm", "dimensionless", "W m-2", "W m-2", "C"]
            }
        }
    }
    
@app.get("/climate-data-timeseries/")
async def get_climate_data_timeseries(
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format (not required for Elevation or SoilGrids)"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format (not required for Elevation or SoilGrids)"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et, elev, sg)"),
    variable: Optional[Variable] = Query(None, description="Climate variable (prec, tmax, tmin, spei, et, elev, bdod, cec, etc.)"),
    db: AsyncSession = Depends(get_db)
):
    # Validate inputs
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    
    # For static data sources (Elevation and SoilGrids), handle differently
    if data_source in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
        # Set default variable based on data source if not provided
        # if variable is None:
        #     if data_source == DataSource.ELEVATION:
        #         variable = Variable.ELEVATION
        #     elif data_source == DataSource.SOILGRIDS:
        #         variable = Variable.BDOD  # Default to bulk density for SoilGrids
        # Set default variable based on data source if not provided
        if variable is None:
            if data_source == DataSource.WORLDCLIM:
                variable = Variable.PRECIPITATION
            elif data_source == DataSource.SPEI:
                variable = Variable.SPEI
            elif data_source == DataSource.CHIRPS:
                variable = Variable.CHIRPS
            elif data_source == DataSource.ET:
                variable = Variable.ET
            elif data_source == DataSource.TERRACLIM:
                variable = Variable.PPT  # Default to precipitation for TerraClim
            elif data_source == DataSource.NASAPOWER:
                variable = Variable.ALLSKY_SFC_SW_DWN  # Default to all-sky surface SW down for NASA POWER
        
        # Validate variable-data source compatibility
        if data_source == DataSource.WORLDCLIM and variable not in [Variable.PRECIPITATION, Variable.TMAX, Variable.TMIN]:
            raise HTTPException(status_code=400, detail=f"WorldClim only supports these variables: prec, tmax, tmin")
        elif data_source == DataSource.SPEI and variable != Variable.SPEI:
            raise HTTPException(status_code=400, detail="SPEI data source only supports spei variable")
        elif data_source == DataSource.CHIRPS and variable != Variable.CHIRPS:
            raise HTTPException(status_code=400, detail="CHIRPS data source only supports chirps variable")
        elif data_source == DataSource.ET and variable != Variable.ET:
            raise HTTPException(status_code=400, detail="ET data source only supports et variable")
        elif data_source == DataSource.TERRACLIM and variable not in [
            Variable.AET, Variable.DEF, Variable.PDSI, Variable.PET, Variable.PPT,
            Variable.Q, Variable.SOIL, Variable.SRAD, Variable.TMAX, Variable.TMIN,
            Variable.VAP, Variable.VPD, Variable.WS
        ]:           
            raise HTTPException(status_code=400, detail="Invalid TerraClim variable")
        elif data_source == DataSource.NASAPOWER and not variable.value.startswith(("allsky_", "clrsky_", "airmass", "aod_", "cloud_", "midday_", "original_", "psh", "pw", "srf_", "toa_", "ts_")):
            raise HTTPException(status_code=400, detail="Invalid NASA POWER variable")
    
        
        # Validate variable-data source compatibility
        if data_source == DataSource.ELEVATION and variable != Variable.ELEVATION:
            raise HTTPException(status_code=400, detail="Elevation data source only supports elev variable")
        elif data_source == DataSource.SOILGRIDS and variable not in [
            Variable.BDOD, Variable.CEC, Variable.CFVO, Variable.CLAY, Variable.NITROGEN,
            Variable.OCD, Variable.OCS, Variable.PHH2O, Variable.SAND, Variable.SILT, Variable.SOC, Variable.WV0010, Variable.WV0030, Variable.WV1500
        ]:
            raise HTTPException(status_code=400, detail="Invalid SoilGrids variable")
        
        # Define the point for PostGIS query
        point = f'POINT({lon} {lat})'
        
        # Get cadence for the selected data source
        cadence = get_cadence_for_data_source(data_source)
        
        # Prepare the results structure
        results = {
            "lon": lon,
            "lat": lat,
            "wkt": f"POINT({lon} {lat})",
            "data_source": data_source.value,
            "variable": variable.value,
            "cadence": cadence.value,
            "values": []
        }
        
        try:
            table_name = get_table_name(data_source, variable)
            
            # Build the query to get the raster value for the point
            query = text(f"""
                SELECT 
                    {lon} AS lon, 
                    {lat} AS lat,
                    ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value
                FROM {table_name} 
                WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                LIMIT 1
            """)
            
            # Execute the query
            result = await db.execute(query)
            row = result.mappings().first()
            
            if not row or row['value'] is None:
                return {
                    "message": f"No data found at specified coordinates for {data_source.value}-{variable.value}",
                    "lon": lon,
                    "lat": lat,
                    "data_source": data_source.value,
                    "variable": variable.value,
                    "cadence": cadence.value,
                    "values": []
                }
            
            # For static data, we still use a time series structure but with a single value
            # This allows the frontend to handle it consistently
            value = row['value']
            
            results["values"].append({
                "value": value,
                # No date/time information for static data
            })
            
            return results
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # For time series data sources, continue with regular processing
    # Require start_date and end_date for time series data
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="start_date and end_date are required for time series data")
    
    # Set default variable based on data source if not provided
    if variable is None:
        if data_source == DataSource.WORLDCLIM:
            variable = Variable.PRECIPITATION
        elif data_source == DataSource.SPEI:
            variable = Variable.SPEI
        elif data_source == DataSource.CHIRPS:
            variable = Variable.CHIRPS
        elif data_source == DataSource.ET:
            variable = Variable.ET
    
    # Validate variable-data source compatibility
    if data_source == DataSource.WORLDCLIM and variable not in [Variable.PRECIPITATION, Variable.TMAX, Variable.TMIN]:
        raise HTTPException(status_code=400, detail=f"WorldClim only supports these variables: prec, tmax, tmin")
    elif data_source == DataSource.SPEI and variable != Variable.SPEI:
        raise HTTPException(status_code=400, detail="SPEI data source only supports spei variable")
    elif data_source == DataSource.CHIRPS and variable != Variable.CHIRPS:
        raise HTTPException(status_code=400, detail="CHIRPS data source only supports chirps variable")
    elif data_source == DataSource.ET and variable != Variable.ET:
        raise HTTPException(status_code=400, detail="ET data source only supports et variable")
    
    # Parse start and end dates for time series data sources
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    if end_date_obj < start_date_obj:
        raise HTTPException(status_code=400, detail="End date must be greater than or equal to start date.")
    
    # Define the point for PostGIS query
    point = f'POINT({lon} {lat})'
    
    # Get cadence for the selected data source
    cadence = get_cadence_for_data_source(data_source)
    
    results = {
        "lon": lon,
        "lat": lat,
        "wkt": f"POINT({lon} {lat})",
        "data_source": data_source.value,
        "variable": variable.value,
        "cadence": cadence.value,
        "values": []
    }
    
    # Function to check if a table exists in the database
    async def table_exists(table_name):
        check_query = text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            );
        """)
        
        try:
            result = await db.execute(check_query)
            return result.scalar()
        except Exception:
            return False
    
    # Handle different cadences with appropriate methods
    if cadence == Cadence.MONTHLY:
        # For WorldClim and SPEI (monthly cadence)
        current_date = datetime(start_date_obj.year, start_date_obj.month, 1)
        end_month = datetime(end_date_obj.year, end_date_obj.month, 1)
        
        while current_date <= end_month:
            year = current_date.year
            month = current_date.month
            date_key = f"{year}-{month:02d}"
            
            try:
                table_name = get_table_name(data_source, variable, year, month)
                
                # Check if table exists before querying
                if await table_exists(table_name):
                    query = text(f"""
                        SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                        FROM {table_name} 
                        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                        LIMIT 1
                    """)
                    
                    try:
                        result = await db.execute(query)
                        row = result.mappings().first()
                        value = row['value'] if row and 'value' in row else None
                        
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "value": value
                        })
                    except Exception as e:
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "value": None,
                            "error": f"Query error: {str(e)}"
                        })
                else:
                    # Table doesn't exist
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "value": None,
                        "error": "No data available for this date"
                    })
            except ValueError as e:
                # Handle errors in table name generation
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "value": None,
                    "error": str(e)
                })
            
            # Move to the next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)
                
    elif cadence == Cadence.DAILY:
        # For CHIRPS (daily cadence)
        current_date = start_date_obj
        
        while current_date <= end_date_obj:
            year = current_date.year
            month = current_date.month
            day = current_date.day
            date_key = f"{year}-{month:02d}-{day:02d}"
            
            try:
                table_name = get_table_name(data_source, variable, year, month, day)
                
                # Check if table exists before querying
                if await table_exists(table_name):
                    query = text(f"""
                        SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                        FROM {table_name} 
                        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                        LIMIT 1
                    """)
                    
                    try:
                        result = await db.execute(query)
                        row = result.mappings().first()
                        value = row['value'] if row and 'value' in row else None
                        
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "day": day,
                            "value": value
                        })
                    except Exception as e:
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "day": day,
                            "value": None,
                            "error": f"Query error: {str(e)}"
                        })
                else:
                    # Table doesn't exist
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": None,
                        "error": "No data available for this date"
                    })
            except ValueError as e:
                # Handle errors in table name generation
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "day": day,
                    "value": None,
                    "error": str(e)
                })
            
            # Move to the next day
            current_date += timedelta(days=1)
            
    elif cadence == Cadence.EIGHT_DAY:
        # For ET (8-day cadence)
        # Get a list of all ET tables in the database that fall within the date range
        
        # Build a query to find all relevant ET tables in the database
        tables_query = text(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name LIKE 'et\_%' 
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        try:
            tables_result = await db.execute(tables_query)
            et_tables = [row['table_name'] for row in tables_result.mappings().all()]
            
            # Filter tables to only include those in the requested date range
            filtered_tables = []
            for table in et_tables:
                # Parse the date from table name (et_YYYY_MM_DD format)
                try:
                    parts = table.split('_')
                    if len(parts) == 4:
                        year = int(parts[1])
                        month = int(parts[2])
                        day = int(parts[3])
                        
                        table_date = datetime(year, month, day)
                        if start_date_obj <= table_date <= end_date_obj:
                            filtered_tables.append({
                                "table": table,
                                "date": table_date,
                                "year": year,
                                "month": month,
                                "day": day
                            })
                except (ValueError, IndexError):
                    # Skip tables that don't match our expected format
                    continue
            
            # Sort the filtered tables by date
            filtered_tables.sort(key=lambda x: x["date"])
            
            # Now query each table in the filtered list
            for table_info in filtered_tables:
                table_name = table_info["table"]
                year = table_info["year"]
                month = table_info["month"]
                day = table_info["day"]
                date_key = f"{year}-{month:02d}-{day:02d}"
                
                # Define the query for this table
                query = text(f"""
                    SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                    FROM {table_name} 
                    WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                    LIMIT 1
                """)
                
                try:
                    result = await db.execute(query)
                    row = result.mappings().first()
                    value = row['value'] if row and 'value' in row else None
                    
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": value
                    })
                except Exception as e:
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": None,
                        "error": f"Query error: {str(e)}"
                    })
        
        except Exception as e:
            # Handle any errors in the table lookup process
            results["error"] = f"Error retrieving ET tables: {str(e)}"
    
    return results

# with open("static/timeseries.html", "w") as f:
#     f.write(html_content)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add an endpoint to serve the HTML
@app.get("/ui/", response_class=HTMLResponse)
async def get_ui():
    with open("static/timeseries.html", "r") as f:
        return f.read()
    
@app.get("/CSVGenerator", response_class=HTMLResponse)
async def get_csv_generator():
    with open("static/csv_generator.html", "r") as f:
        return f.read()
    
@app.post("/api/process-csv")
async def process_csv(
    file: UploadFile = File(...),
    option: str = Form(...)
):
    # Validate file type
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="Only CSV or XLSX files are accepted")
    
    # Generate unique ID for this processing job
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"../Csv-Creator/uploads/{job_id}")
    processed_dir = Path(f"../Csv-Creator/processed/{job_id}")
    
    # Create directories
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    
    # Save the uploaded file
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Path for the results
    raw_data_path = processed_dir / f"raw_data_{file.filename}"
    covariates_path = processed_dir / f"covariates_{file.filename}"
    
    # Run the script to generate raw data
    try:
        # Replace with the path to your script
        raw_data_script = "../Csv-Creator/script.py"
        subprocess.run([
            "python", raw_data_script,
            "--input", str(file_path),
            "--output", str(raw_data_path),
            "--default-start-date", "2000-01-01",
            "--default-end-date", "2000-12-31",
            "--all-variables",
            "--cache-file", f"{processed_dir}/cache.json"
        ], check=True)
        
        # For "full" option, also generate covariates
        if option == "full":
            covariates_script = "../Csv-Creator/covariablesv3.py"
            subprocess.run([
            "python", covariates_script,
            "--input", str(raw_data_path),
            "--output", str(covariates_path)
        ], check=True)
            
            return {
                "rawDataFile": f"/download/{job_id}/raw_data_{file.filename}",
                "covariatesFile": f"/download/{job_id}/covariates_{file.filename}"
            }
        else:
            return {
                "rawDataFile": f"/download/{job_id}/raw_data_{file.filename}"
            }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Endpoint to download processed files
@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    file_path = Path(f"processed/{job_id}/{filename}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cleanup logic on startup
    base_dir = Path(__file__).resolve().parent.parent  # Points to Api-v1/
    csv_creator_path = (base_dir / "../Csv-Creator").resolve()

    for subdir in ["uploads", "processed"]:
        dir_path = csv_creator_path / subdir
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            dir_path.mkdir(parents=True)

    print("🧹 Cleaned uploads/ and processed/ directories on startup.")
    
    yield