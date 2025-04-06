from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from typing import Optional, List, Literal, Callable
from datetime import datetime, timedelta
from enum import Enum
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os



os.makedirs("static", exist_ok=True)

# Create the HTML file in the static directory
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Climate Data Time Series Interface</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: Arial, sans-serif;
        }
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        .top-section {
            display: flex;
            height: 60%;
        }
        #map {
            flex: 2;
            width: 100%;
        }
        .controls {
            flex: 1;
            padding: 20px;
            background-color: #f5f5f5;
            overflow-y: auto;
        }
        .chart-section {
            height: 40%;
            padding: 20px;
            background-color: #fff;
            border-top: 1px solid #ddd;
        }
        h3 {
            margin-top: 0;
            margin-bottom: 15px;
            color: #333;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        select, input {
            width: 100%;
            padding: 8px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            padding: 10px 15px;
            margin-bottom: 10px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 4px;
            width: 100%;
        }
        button:hover {
            background-color: #45a049;
        }
        .coordinates {
            margin-top: 15px;
            padding: 10px;
            background-color: #e9e9e9;
            border-radius: 4px;
        }
        .loading {
            display: none;
            margin-top: 10px;
            color: #666;
        }
        .error {
            color: #d9534f;
            margin-top: 10px;
        }
        #chartContainer {
            width: 100%;
            height: 100%;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-section">
            <div id="map"></div>
            <div class="controls">
                <h3>Time Series Data</h3>
                
                <div class="coordinates" id="selected-point">
                    <p>Click on the map to select a point.</p>
                </div>
                
                <label for="data-source">Data Source:</label>
                <select id="data-source">
                    <option value="wc">WorldClim</option>
                    <option value="spei">SPEI</option>
                    <option value="chirps">CHIRPS</option>
                    <option value="et">ET</option>
                </select>
                
                <label for="variable">Variable:</label>
                <select id="variable">
                    <option value="prec">Precipitation</option>
                    <option value="tmax">Max Temperature</option>
                    <option value="tmin">Min Temperature</option>
                </select>
                
                <label for="start-date">Start Date:</label>
                <input type="date" id="start-date">
                
                <label for="end-date">End Date:</label>
                <input type="date" id="end-date">
                
                <button id="fetch-data">Fetch Time Series Data</button>
                <button id="clear-selection">Clear Selection</button>
                
                <div id="loading" class="loading">Loading data...</div>
                <div id="error" class="error"></div>
            </div>
        </div>
        <div class="chart-section">
            <div id="chartContainer">
                <canvas id="timeSeriesChart"></canvas>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.js"></script>
    <script>
        // Initialize map
        const map = L.map('map').setView([0, 0], 2);
        
        // Add OpenStreetMap tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        // Define the bounding box (-94.187, -39.020, 37.062, 18.229)
        const bboxCoords = [
            [-39.020, -94.187], // Southwest corner (lat, lng)
            [18.229, 37.062]    // Northeast corner (lat, lng)
        ];
        
        // Display the bounding box on the map
        const bbox = L.rectangle(bboxCoords, {
            color: "#ff7800",
            weight: 2,
            fillOpacity: 0.1
        }).addTo(map);
        
        // Fit map to the bounding box
        map.fitBounds(bboxCoords);
        
        // Variables to store selected point
        let selectedPoint = null;
        let selectedMarker = null;
        let timeSeriesChart = null;
        
        // Update variable dropdown based on selected data source
        document.getElementById('data-source').addEventListener('change', function() {
            const dataSource = this.value;
            const variableSelect = document.getElementById('variable');
            
            // Clear current options
            variableSelect.innerHTML = '';
            
            // Add appropriate options based on data source
            if (dataSource === 'wc') {
                addOption(variableSelect, 'prec', 'Precipitation');
                addOption(variableSelect, 'tmax', 'Max Temperature');
                addOption(variableSelect, 'tmin', 'Min Temperature');
            } else if (dataSource === 'spei') {
                addOption(variableSelect, 'spei', 'SPEI');
            } else if (dataSource === 'chirps') {
                addOption(variableSelect, 'chirps', 'Precipitation');
            } else if (dataSource === 'et') {
                addOption(variableSelect, 'et', 'Evapotranspiration');
            }
        });
        
        // Handle map click event
        map.on('click', function(e) {
            const lat = e.latlng.lat.toFixed(6);
            const lon = e.latlng.lng.toFixed(6);
            
            // Update selected point
            selectedPoint = { lat, lon };
            
            // Update UI
            document.getElementById('selected-point').innerHTML = `
                <strong>Selected Point:</strong><br>
                Latitude: ${lat}<br>
                Longitude: ${lon}
            `;
            
            // Remove previous marker if exists
            if (selectedMarker) {
                map.removeLayer(selectedMarker);
            }
            
            // Add new marker
            selectedMarker = L.marker([lat, lon]).addTo(map);
        });
        
        // Fetch time series data button click handler
        document.getElementById('fetch-data').addEventListener('click', async function() {
            // Check if a point is selected
            if (!selectedPoint) {
                showError('Please select a point on the map first.');
                return;
            }
            
            // Get form values
            const dataSource = document.getElementById('data-source').value;
            const variable = document.getElementById('variable').value;
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            
            // Validate dates
            if (!startDate || !endDate) {
                showError('Please select start and end dates.');
                return;
            }
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').textContent = '';
            
            try {
                // Build API URL
                const apiUrl = `/climate-data-timeseries/?lat=${selectedPoint.lat}&lon=${selectedPoint.lon}&start_date=${startDate}&end_date=${endDate}&data_source=${dataSource}&variable=${variable}`;
                
                // Fetch data
                const response = await fetch(apiUrl);
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Failed to fetch data');
                }
                
                const data = await response.json();
                
                // Process and display the data
                displayTimeSeriesData(data);
            } catch (error) {
                showError(error.message);
            } finally {
                // Hide loading
                document.getElementById('loading').style.display = 'none';
            }
        });
        
        // Clear selection button click handler
        document.getElementById('clear-selection').addEventListener('click', function() {
            // Clear selected point
            selectedPoint = null;
            
            // Remove marker if exists
            if (selectedMarker) {
                map.removeLayer(selectedMarker);
                selectedMarker = null;
            }
            
            // Reset UI
            document.getElementById('selected-point').innerHTML = '<p>Click on the map to select a point.</p>';
            
            // Clear chart
            if (timeSeriesChart) {
                timeSeriesChart.destroy();
                timeSeriesChart = null;
            }
        });
        
        // Function to display time series data
        function displayTimeSeriesData(data) {
            // Prepare chart data
            const chartLabels = [];
            const chartData = [];
            
            // Process values based on cadence
            data.values.forEach(entry => {
                if (entry.value !== null) {
                    // Format date label based on cadence
                    let dateLabel;
                    if (data.cadence === 'monthly') {
                        dateLabel = `${entry.year}-${entry.month.toString().padStart(2, '0')}`;
                    } else {
                        dateLabel = entry.date;
                    }
                    
                    chartLabels.push(dateLabel);
                    chartData.push(entry.value);
                }
            });
            
            // Create chart
            const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            
            // Destroy previous chart if exists
            if (timeSeriesChart) {
                timeSeriesChart.destroy();
            }
            
            // Create new chart
            timeSeriesChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: getVariableLabel(data.variable, data.data_source),
                        data: chartData,
                        borderColor: getChartColor(data.variable),
                        backgroundColor: getChartColor(data.variable, 0.1),
                        tension: 0.1,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: false,
                            title: {
                                display: true,
                                text: getUnitLabel(data.variable, data.data_source)
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: getCadenceLabel(data.cadence)
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: `${getVariableLabel(data.variable, data.data_source)} at Lat: ${data.lat}, Lon: ${data.lon}`
                        },
                        legend: {
                            display: true
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.raw} ${getUnitLabel(data.variable, data.data_source)}`;
                                }
                            }
                        }
                    }
                }
            });
        }
        
        // Helper functions
        function addOption(select, value, text) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = text;
            select.appendChild(option);
        }
        
        function showError(message) {
            document.getElementById('error').textContent = message;
            document.getElementById('loading').style.display = 'none';
        }
        
        function getChartColor(variable, alpha = 1) {
            const colors = {
                'prec': `rgba(0, 119, 190, ${alpha})`,
                'chirps': `rgba(0, 119, 190, ${alpha})`,
                'tmax': `rgba(255, 69, 0, ${alpha})`,
                'tmin': `rgba(30, 144, 255, ${alpha})`,
                'spei': `rgba(50, 205, 50, ${alpha})`,
                'et': `rgba(128, 0, 128, ${alpha})`
            };
            
            return colors[variable] || `rgba(100, 100, 100, ${alpha})`;
        }
        
        function getVariableLabel(variable, dataSource) {
            const labels = {
                'prec': 'Precipitation',
                'chirps': 'Precipitation',
                'tmax': 'Maximum Temperature',
                'tmin': 'Minimum Temperature',
                'spei': 'SPEI',
                'et': 'Evapotranspiration'
            };
            
            return labels[variable] || variable;
        }
        
        function getUnitLabel(variable, dataSource) {
            if (variable === 'prec' || variable === 'chirps' || variable === 'et') {
                return 'mm';
            } else if (variable === 'tmax' || variable === 'tmin') {
                return '°C';
            } else if (variable === 'spei') {
                return 'Index';
            }
            
            return '';
        }
        
        function getCadenceLabel(cadence) {
            const labels = {
                'daily': 'Date',
                '8day': 'Date',
                'monthly': 'Month'
            };
            
            return labels[cadence] || 'Date';
        }
        
        // Set default dates (last 6 months)
        function setDefaultDates() {
            const today = new Date();
            const sixMonthsAgo = new Date();
            sixMonthsAgo.setMonth(today.getMonth() - 6);
            
            document.getElementById('end-date').value = formatDate(today);
            document.getElementById('start-date').value = formatDate(sixMonthsAgo);
        }
        
        function formatDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            
            return `${year}-${month}-${day}`;
        }
        
        // Initialize default dates
        setDefaultDates();
    </script>
</body>
</html>
"""

class DataSource(str, Enum):
    WORLDCLIM = "wc"
    SPEI = "spei"
    CHIRPS = "chirps"
    ET = "et"

class Variable(str, Enum):
    CHIRPS = "chirps"
    PRECIPITATION = "prec"
    TMAX = "tmax"
    TMIN = "tmin"
    SPEI = "spei"
    ET = "et"

class Cadence(str, Enum):
    DAILY = "daily"         # For CHIRPS
    EIGHT_DAY = "8day"      # For ET
    MONTHLY = "monthly"     # For WorldClim, SPEI

app = FastAPI(title="Camcore Database API")


# Helper function to get appropriate table name based on data source and time parameters
def get_table_name(data_source: DataSource, variable: Variable, year: int, month: int, day: Optional[int] = None):
    if data_source == DataSource.WORLDCLIM:
        # WorldClim uses wc_prec_1990_01, wc_tmax_1990_01, wc_tmin_1990_01 format
        return f"{data_source.value}_{variable.value}_{year}_{month:02d}"
    
    elif data_source == DataSource.SPEI:
        # SPEI uses spei_year_month format
        return f"{data_source.value}_{year}_{month:02d}"
    
    elif data_source == DataSource.CHIRPS:
        # CHIRPS is daily - chirps_year_month_day
        if day is None:
            raise ValueError("Day is required for CHIRPS data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    
    elif data_source == DataSource.ET:
        # ET is 8-day cadence - et_year_month_day
        if day is None:
            raise ValueError("Day is required for ET data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    
    else:
        raise ValueError(f"Unknown data source: {data_source}")

# Helper function to get appropriate cadence based on data source
def get_cadence_for_data_source(data_source: DataSource):
    if data_source == DataSource.WORLDCLIM or data_source == DataSource.SPEI:
        return Cadence.MONTHLY
    elif data_source == DataSource.CHIRPS:
        return Cadence.DAILY
    elif data_source == DataSource.ET:
        return Cadence.EIGHT_DAY
    else:
        raise ValueError(f"Unknown data source: {data_source}")

def validate_date_params(data_source: DataSource, year: int, month: int, day: Optional[int] = None):
    cadence = get_cadence_for_data_source(data_source)
    
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    if cadence == Cadence.DAILY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for CHIRPS data source")
        days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # Accounting for leap year max
        if not (1 <= day <= days_in_month[month]):
            raise HTTPException(status_code=400, detail=f"Day must be between 1 and {days_in_month[month]} for month {month}")
    
    # In your validate_date_params function
    elif cadence == Cadence.EIGHT_DAY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for ET data source")
        
        # Check if the date follows the 8-day cadence
        try:
            check_date = datetime(year, month, day)
            baseline = datetime(2000, 1, 1)
            
            # Check if date is on or after baseline
            if check_date < baseline:
                raise HTTPException(
                    status_code=400, 
                    detail=f"ET data is only available from 2000-01-01 onwards."
                )
            
            # Check if it falls on the 8-day cadence
            days_diff = (check_date - baseline).days
            if days_diff % 8 != 0:
                # Calculate the next valid ET date
                days_to_next = 8 - (days_diff % 8)
                next_valid_date = check_date + timedelta(days=days_to_next)
                
                # Calculate the previous valid ET date
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
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et)")
) -> Optional[Variable]:
    """Dependency that only requests variable parameter if data_source is WorldClim"""
    if data_source == DataSource.WORLDCLIM:
        return Query(None, description="Climate variable (prec, tmax, tmin)")
    return None
       
def is_valid_et_date(date_obj: datetime) -> bool:
    """Check if a date is a valid ET date (follows the 8-day cadence from 2000-01-01)"""
    # Establish the start reference date (January 1, 2000)
    start_date = datetime(2000, 1, 1)
    
    # If the requested date is before the start date, it's invalid
    if date_obj < start_date:
        return False
    
    # Calculate days difference between the requested date and the start date
    days_diff = (date_obj - start_date).days
    
    # Check if it falls on an 8-day interval (0, 8, 16, etc.)
    return days_diff % 8 == 0

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Camcore Database API",
        "available_data_sources": {
            "wc": "WorldClim (monthly: precipitation, tmax, tmin)",
            "spei": "SPEI (monthly)",
            "chirps": "CHIRPS (daily precipitation)",
            "et": "Evapotranspiration (8-day cadence)"
        }
    }
@app.get("/climate-data-point/")
async def get_climate_data_point(
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    year: int = Query(..., description="Year (e.g., 1990)"),
    month: int = Query(..., description="Month (1-12)"),
    day: Optional[int] = Query(None, description="Day (required for CHIRPS and ET data sources)"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et)"),
    variable: Optional[Variable] = Query(None, description="Climate variable (prec, tmax, tmin, spei, et)"),
    db: AsyncSession = Depends(get_db)
):
    # Validate inputs
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    
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
    elif data_source == DataSource.CHIRPS and variable != Variable.PRECIPITATION:
        raise HTTPException(status_code=400, detail="CHIRPS data source only supports prec variable")
    elif data_source == DataSource.ET and variable != Variable.ET:
        raise HTTPException(status_code=400, detail="ET data source only supports et variable")
    
    # Define the point
    point = f'POINT({lon} {lat})'
    
    # For ET data source, we need to handle it differently
    if data_source == DataSource.ET:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for ET data source")
        
        # Convert the requested date to datetime for comparison
        try:
            requested_date = datetime(year, month, day)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date")
        
        # Find the nearest ET table to the requested date
        find_tables_query = text(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name LIKE 'et\_%' 
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        try:
            tables_result = await db.execute(find_tables_query)
            et_tables = [row['table_name'] for row in tables_result.mappings().all()]
            
            # Find the closest table to the requested date
            closest_table = None
            smallest_diff = float('inf')
            table_date = None
            
            for table in et_tables:
                # Parse the date from table name (et_YYYY_MM_DD format)
                try:
                    parts = table.split('_')
                    if len(parts) == 4:
                        t_year = int(parts[1])
                        t_month = int(parts[2])
                        t_day = int(parts[3])
                        
                        table_date_obj = datetime(t_year, t_month, t_day)
                        diff = abs((table_date_obj - requested_date).total_seconds())
                        
                        if diff < smallest_diff:
                            smallest_diff = diff
                            closest_table = table
                            table_date = table_date_obj
                except (ValueError, IndexError):
                    # Skip tables that don't match our expected format
                    continue
            
            if closest_table is None:
                raise HTTPException(status_code=404, detail="No ET data found near the requested date")
            
            # Use the closest table for the query
            # Extract the actual date from the table name
            table_parts = closest_table.split('_')
            actual_year = int(table_parts[1])
            actual_month = int(table_parts[2])
            actual_day = int(table_parts[3])
            
            query = text(f"""
                SELECT 
                    {lon} AS lon, 
                    {lat} AS lat,
                    ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value,
                    ST_AsText(ST_SetSRID(ST_PointFromText('{point}'), 4326)) AS wkt
                FROM {closest_table} 
                WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                LIMIT 1
            """)
            
            # Execute the query
            result = await db.execute(query)
            row = result.mappings().first()
            
            if not row:
                return {
                    "message": f"No data found at specified coordinates for the given parameters",
                    "nearest_available_date": f"{actual_year}-{actual_month:02d}-{actual_day:02d}"
                }
            
            # Include the actual date in the response
            response = dict(row)
            response["data_source"] = data_source.value
            response["variable"] = variable.value
            response["requested_date"] = f"{year}-{month:02d}-{day:02d}"
            response["actual_date"] = f"{actual_year}-{actual_month:02d}-{actual_day:02d}"
            response["year"] = actual_year
            response["month"] = actual_month
            response["day"] = actual_day
            
            return response
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # For other data sources, continue with the original approach
    # Validate date parameters based on data source
    try:
        validate_date_params(data_source, year, month, day)
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Get appropriate table name
    try:
        table_name = get_table_name(data_source, variable, year, month, day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Build the query to get the raster value for the point
    query = text(f"""
        SELECT 
            {lon} AS lon, 
            {lat} AS lat,
            ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value,
            ST_AsText(ST_SetSRID(ST_PointFromText('{point}'), 4326)) AS wkt
        FROM {table_name} 
        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
        LIMIT 1
    """)
    
    try:
        # Execute the raw SQL query
        result = await db.execute(query)
        
        # Fetch the result as a dictionary
        row = result.mappings().first()
        
        if not row:
            return {"message": f"No data found at specified coordinates for the given parameters"}
        
        # Convert to a proper response format
        response = dict(row)
        response["data_source"] = data_source.value
        response["variable"] = variable.value
        response["year"] = year
        response["month"] = month
        
        cadence = get_cadence_for_data_source(data_source)
        if cadence in [Cadence.DAILY, Cadence.EIGHT_DAY]:
            response["day"] = day
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/climate-data-timeseries/")
async def get_climate_data_timeseries(
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et)"),
    variable: Optional[Variable] = Query(None, description="Climate variable (prec, tmax, tmin, spei, et)"),
    db: AsyncSession = Depends(get_db)
):
    # Validate inputs
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    
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
    
    # Parse start and end dates
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
            
            current_et_date += timedelta(days=8)
    
    return results
with open("static/timeseries.html", "w") as f:
    f.write(html_content)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add an endpoint to serve the HTML
@app.get("/ui/", response_class=HTMLResponse)
async def get_ui():
    with open("static/timeseries.html", "r") as f:
        return f.read()


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
            }
        }
    }