// src/specialized-views/WaterDeficitDashboard.jsx
import React, { useState, useEffect, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl';
import {
    LineChart,
    Line,
    BarChart,
    Bar,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { processData, calculateStats } from '../utils/dataProcessing';
import config from '../config';

// Default GEE bounding box
const DEFAULT_BBOX = {
    west: -94.187,
    south: -39.020,
    east: 37.062,
    north: 18.229
};
const baseUrl = "http://localhost:8000/climate-data-timeseries/"; // Replace with your actual API base URL
// Get center of bounding box
const getBboxCenter = (bbox) => {
    return {
        longitude: (bbox.west + bbox.east) / 2,
        latitude: (bbox.south + bbox.north) / 2
    };
};

// Calculate appropriate zoom level based on bounding box size
const calculateZoom = (bbox) => {
    const longitudeSpan = Math.abs(bbox.east - bbox.west);
    const latitudeSpan = Math.abs(bbox.north - bbox.south);
    const maxSpan = Math.max(longitudeSpan, latitudeSpan);
    // Simple formula to estimate zoom level - might need adjustment
    return Math.log2(360 / maxSpan) - 1;
};

// Convert bbox to GeoJSON
const bboxToGeoJson = (bbox) => {
    return {
        type: 'Feature',
        properties: {},
        geometry: {
            type: 'Polygon',
            coordinates: [[
                [bbox.west, bbox.north],
                [bbox.east, bbox.north],
                [bbox.east, bbox.south],
                [bbox.west, bbox.south],
                [bbox.west, bbox.north]
            ]]
        }
    };
};

// Water Deficit Dashboard Component
const WaterDeficitDashboard = ({ timeSeriesData, onLocationChange }) => {
    const [processedData, setProcessedData] = useState([]);
    const [stats, setStats] = useState(null);
    const [currentLocation, setCurrentLocation] = useState(null);

    // Manual input for coordinates
    const [manualLon, setManualLon] = useState('');
    const [manualLat, setManualLat] = useState('');

    // Manual input for bbox
    const [manualBbox, setManualBbox] = useState({
        west: DEFAULT_BBOX.west.toString(),
        south: DEFAULT_BBOX.south.toString(),
        east: DEFAULT_BBOX.east.toString(),
        north: DEFAULT_BBOX.north.toString()
    });

    // Calculate initial view state based on default bbox
    const center = getBboxCenter(DEFAULT_BBOX);
    const initialZoom = calculateZoom(DEFAULT_BBOX);

    const [viewState, setViewState] = useState({
        longitude: center.longitude,
        latitude: center.latitude,
        zoom: initialZoom,
        pitch: 0,
        bearing: 0
    });

    const [currentTimeIndex, setCurrentTimeIndex] = useState(0);
    const [animationPlaying, setAnimationPlaying] = useState(false);
    const [hoverInfo, setHoverInfo] = useState(null);
    const [selectedBbox, setSelectedBbox] = useState(DEFAULT_BBOX);
    const [isSelectingLocation, setIsSelectingLocation] = useState(false);
    const [debugInfo, setDebugInfo] = useState({});
    const [queriedUrl, setQueriedUrl] = useState('');


    // Reference to track click position for location selection
    const clickPositionRef = useRef(null);

    // Process data when it's loaded
    useEffect(() => {
        if (timeSeriesData) {
            console.log("Processing time series data:", timeSeriesData);
            try {
                const processed = processData(timeSeriesData);
                console.log("Processed data:", processed);
                setProcessedData(processed);

                // Update debug info
                setDebugInfo({
                    hasData: processed && processed.length > 0,
                    dataPoints: processed ? processed.length : 0,
                    samplePoint: processed && processed.length > 0 ? {
                        lon: processed[0].lon,
                        lat: processed[0].lat,
                        def: processed[0].def
                    } : null,
                    bboxUsed: selectedBbox,
                    locationUsed: currentLocation
                });

                // Calculate statistics
                if (processed && processed.length > 0) {
                    const statistics = calculateStats(processed, 'def');
                    setStats(statistics);

                    // Center map on data point if no user selection yet
                    if (processed[0]) {
                        setViewState(prevState => ({
                            ...prevState,
                            longitude: processed[0].lon,
                            latitude: processed[0].lat
                        }));
                    }
                }
            } catch (error) {
                console.error("Error processing data:", error);
                setDebugInfo(prevInfo => ({
                    ...prevInfo,
                    error: error.message
                }));
            }
        } else {
            console.log("No time series data provided");
        }
    }, [timeSeriesData]);

    // Animation effect
    useEffect(() => {
        let animationFrame;
        if (animationPlaying && processedData.length > 0) {
            animationFrame = setTimeout(() => {
                setCurrentTimeIndex(prevIndex => {
                    const nextIndex = prevIndex + 1;
                    // Reset to beginning if we reach the end
                    return nextIndex >= processedData.length ? 0 : nextIndex;
                });
            }, 700); // Animation speed
        }
        return () => {
            if (animationFrame) {
                clearTimeout(animationFrame);
            }
        };
    }, [animationPlaying, currentTimeIndex, processedData.length]);

    // Current data frame for animation
    const currentData = processedData.length > 0 ? [processedData[currentTimeIndex]] : [];

    // You'll call this whenever you fetch data
    const updateQueriedUrl = () => {
        // This is an example - you'll need to modify based on your actual API structure
        const baseUrl = "http://localhost:8000/climate-data-timeseries/"; // Replace with your actual API base URL
        const endpoint = '/water-deficit';
        const params = new URLSearchParams({
            west: selectedBbox.west.toFixed(3),
            south: selectedBbox.south.toFixed(3),
            east: selectedBbox.east.toFixed(3),
            north: selectedBbox.north.toFixed(3),
            // Add other parameters as needed
            start_date: timeSeriesData?.start_date || '',
            end_date: timeSeriesData?.end_date || ''
        });

        const url = `${baseUrl}${endpoint}?${params.toString()}`;
        setQueriedUrl(url);

        // Add to debug info
        setDebugInfo(prevInfo => ({
            ...prevInfo,
            queriedUrl: url
        }));

        return url;
    };

    // Handle map click for location selection
    const handleMapClick = (event) => {
        if (isSelectingLocation && event.coordinate) {
            const [longitude, latitude] = event.coordinate;

            // Update manual coordinate inputs
            setManualLon(longitude.toFixed(6));
            setManualLat(latitude.toFixed(6));

            const newLocation = { longitude, latitude };
            setCurrentLocation(newLocation);
            console.log("Selected location:", longitude, latitude);

            // Call external handler if provided
            if (onLocationChange) {
                onLocationChange(newLocation);
            }

            setIsSelectingLocation(false);
        }
    };

    // Handle manual location submission
    const handleManualLocationSubmit = (e) => {
        e.preventDefault();

        try {
            const longitude = parseFloat(manualLon);
            const latitude = parseFloat(manualLat);

            if (isNaN(longitude) || isNaN(latitude)) {
                throw new Error("Invalid coordinates");
            }

            if (longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
                throw new Error("Coordinates out of range");
            }

            const newLocation = { longitude, latitude };
            setCurrentLocation(newLocation);

            // Update view to center on the new location
            setViewState(prevState => ({
                ...prevState,
                longitude,
                latitude
            }));

            // Call external handler if provided
            if (onLocationChange) {
                onLocationChange(newLocation);
            }

            console.log("Manual location set:", longitude, latitude);
        } catch (error) {
            console.error("Error setting manual location:", error);
            alert(`Error setting location: ${error.message}`);
        }
    };

    // Handle manual bbox submission
    const handleManualBboxSubmit = (e) => {
        e.preventDefault();

        try {
            const west = parseFloat(manualBbox.west);
            const south = parseFloat(manualBbox.south);
            const east = parseFloat(manualBbox.east);
            const north = parseFloat(manualBbox.north);

            if ([west, south, east, north].some(isNaN)) {
                throw new Error("Invalid bbox coordinates");
            }

            // Basic validation
            if (west < -180 || west > 180 || east < -180 || east > 180 ||
                south < -90 || south > 90 || north < -90 || north > 90) {
                throw new Error("Coordinates out of range");
            }

            const newBbox = { west, south, east, north };
            setSelectedBbox(newBbox);

            // Update view to show the new bbox
            const center = getBboxCenter(newBbox);
            const zoom = calculateZoom(newBbox);

            setViewState({
                longitude: center.longitude,
                latitude: center.latitude,
                zoom,
                pitch: 0,
                bearing: 0
            });

            console.log("Manual bbox set:", newBbox);

            // Update debug info
            setDebugInfo(prevInfo => ({
                ...prevInfo,
                bboxUsed: newBbox
            }));
        } catch (error) {
            console.error("Error setting manual bbox:", error);
            alert(`Error setting bbox: ${error.message}`);
        }
    };

    // Map layers
    const getLayers = () => {
        const layers = [];

        // Add bounding box visualization
        layers.push(
            new GeoJsonLayer({
                id: 'bbox-layer',
                data: bboxToGeoJson(selectedBbox),
                stroked: true,
                filled: true,
                lineWidthMinPixels: 2,
                getLineColor: [0, 0, 255, 200],
                getFillColor: [0, 0, 255, 20]
            })
        );

        // Add selected location marker if any
        if (currentLocation) {
            layers.push(
                new ScatterplotLayer({
                    id: 'selected-location',
                    data: [currentLocation],
                    pickable: true,
                    stroked: true,
                    filled: true,
                    radiusScale: 6,
                    radiusMinPixels: 8,
                    radiusMaxPixels: 8,
                    lineWidthMinPixels: 1,
                    getPosition: d => [d.longitude, d.latitude],
                    getFillColor: [255, 0, 0, 255],
                    getLineColor: [255, 255, 255]
                })
            );
        }

        // Add data visualization layers if data is available
        if (processedData.length) {
            console.log("Adding data visualization layers with", processedData.length, "data points");

            // Points/Scatter layer for precise locations
            layers.push(
                new ScatterplotLayer({
                    id: 'water-deficit-points',
                    data: animationPlaying ? currentData : processedData,
                    pickable: true,
                    stroked: true,
                    filled: true,
                    radiusScale: 30000,
                    radiusMinPixels: 5,
                    radiusMaxPixels: 50,
                    lineWidthMinPixels: 1,
                    getPosition: d => [d.lon, d.lat],
                    getRadius: d => Math.max(Math.sqrt(d.def) * 100, 1000),  // Ensure points are visible
                    getFillColor: d => getColorForDeficit(d.def),
                    getLineColor: [255, 255, 255],
                    onHover: info => setHoverInfo(info.object ? info : null),
                    updateTriggers: {
                        data: animationPlaying ? currentTimeIndex : processedData
                    }
                })
            );

            // Heatmap layer for overall pattern visualization
            layers.push(
                new HeatmapLayer({
                    id: 'water-deficit-heatmap',
                    data: animationPlaying ? currentData : processedData,
                    getPosition: d => [d.lon, d.lat],
                    getWeight: d => d.def,
                    radiusPixels: 60,
                    intensity: 1,
                    threshold: 0.03,
                    colorRange: [
                        [49, 163, 84, 50],    // Low deficit
                        [173, 221, 142, 100],
                        [247, 252, 185, 150],
                        [252, 252, 204, 200],
                        [252, 146, 114, 220],
                        [222, 45, 38, 255]    // High deficit
                    ],
                    updateTriggers: {
                        data: animationPlaying ? currentTimeIndex : processedData
                    }
                })
            );
        } else {
            console.log("No data available for visualization layers");
        }

        return layers;
    };

    // Get color based on deficit value
    const getColorForDeficit = (value) => {
        if (value <= 20) return [49, 163, 84];  // Low
        if (value <= 40) return [173, 221, 142];
        if (value <= 60) return [247, 252, 185];
        if (value <= 80) return [252, 146, 114];
        return [222, 45, 38];  // High
    };

    // Format a date string
    const formatDateStr = (date) => {
        if (!date) return '';
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    // Render time series chart
    const renderTimeSeriesChart = () => {
        if (!processedData.length) return (
            <div className="timeseries-chart">
                <h3>Water Deficit Time Series</h3>
                <p>No data available. Please select a location or adjust your filters.</p>
            </div>
        );

        return (
            <div className="timeseries-chart">
                <h3>Water Deficit Time Series</h3>

                <div className="debug-info">
                    <details open>
                        <summary>Debug Info</summary>
                        <p>Has Data: {processedData.length > 0 ? 'Yes' : 'No'}</p>
                        <p>Data Points: {processedData.length}</p>

                        {/* Add this section to display the queried URL */}
                        <div className="queried-url">
                            <p><strong>Last Queried URL:</strong></p>
                            <div className="url-box">
                                {queriedUrl || 'No query performed yet'}
                            </div>
                        </div>

                        {processedData.length > 0 && (
                            <div>
                                <p>Sample Points (first 3):</p>
                                <ul>
                                    {processedData.slice(0, 3).map((point, idx) => (
                                        <li key={idx}>
                                            Point {idx + 1}: Lon {point.lon.toFixed(3)}, Lat {point.lat.toFixed(3)}, Def {point.def.toFixed(2)}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        <p>Current Bounding Box:</p>
                        <ul>
                            <li>West: {selectedBbox.west.toFixed(3)}</li>
                            <li>South: {selectedBbox.south.toFixed(3)}</li>
                            <li>East: {selectedBbox.east.toFixed(3)}</li>
                            <li>North: {selectedBbox.north.toFixed(3)}</li>
                        </ul>
                        <p>Map Center: {viewState.longitude.toFixed(3)}, {viewState.latitude.toFixed(3)}</p>
                        <p>Map Zoom: {viewState.zoom.toFixed(2)}</p>
                        {currentLocation && (
                            <p>Selected Location: {currentLocation.longitude.toFixed(3)}, {currentLocation.latitude.toFixed(3)}</p>
                        )}
                        {debugInfo.error && (
                            <p className="error">Error: {debugInfo.error}</p>
                        )}
                    </details>
                </div>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart
                        data={processedData}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            dataKey="date"
                            tickFormatter={formatDateStr}
                            label={{ value: 'Date', position: 'insideBottomRight', offset: -10 }}
                        />
                        <YAxis
                            label={{ value: 'Water Deficit (mm)', angle: -90, position: 'insideLeft' }}
                        />
                        <Tooltip
                            labelFormatter={formatDateStr}
                            formatter={(value) => [`${Math.round(value * 10) / 10} mm`, 'Water Deficit']}
                        />
                        <Legend />
                        <Bar
                            dataKey="def"
                            name="Water Deficit"
                            fill="#de2d26"
                            background={{ fill: '#eee' }}
                            isAnimationActive={false}
                        />
                    </BarChart>
                </ResponsiveContainer>
                <div className="animation-controls">
                    <button
                        className={`play-button ${animationPlaying ? 'playing' : ''}`}
                        onClick={() => setAnimationPlaying(!animationPlaying)}
                    >
                        {animationPlaying ? '⏸ Pause' : '▶ Play Time Lapse'}
                    </button>
                    {animationPlaying && processedData.length > 0 && (
                        <div className="current-time">
                            Showing: {formatDateStr(processedData[currentTimeIndex]?.date)}
                        </div>
                    )}
                    <input
                        type="range"
                        min={0}
                        max={processedData.length - 1}
                        value={currentTimeIndex}
                        onChange={(e) => setCurrentTimeIndex(parseInt(e.target.value))}
                        disabled={processedData.length <= 1}
                    />
                </div>
            </div>
        );
    };

    // Main render
    return (
        <div className="water-deficit-dashboard">
            <header className="dashboard-header">
                <h1>Water Deficit Analysis Dashboard</h1>
                {timeSeriesData && (
                    <p className="location-info">
                        Location: {timeSeriesData.location?.lat.toFixed(2) || 'N/A'}, {timeSeriesData.location?.lon.toFixed(2) || 'N/A'} |
                        Period: {timeSeriesData.start_date || 'N/A'} to {timeSeriesData.end_date || 'N/A'}
                    </p>
                )}
                {!timeSeriesData && (
                    <p className="location-info warning">
                        No data loaded. Please select a location or time range.
                    </p>
                )}
            </header>

            <div className="dashboard-grid">
                <div className="map-section">
                    <div className="map-controls">
                        <button
                            className={`control-button ${isSelectingLocation ? 'active' : ''}`}
                            onClick={() => setIsSelectingLocation(!isSelectingLocation)}
                        >
                            {isSelectingLocation ? 'Click on map to select location' : 'Select Location'}
                        </button>
                        <button
                            className="control-button"
                            onClick={() => {
                                // Reset to default bounding box
                                const center = getBboxCenter(DEFAULT_BBOX);
                                setViewState({
                                    longitude: center.longitude,
                                    latitude: center.latitude,
                                    zoom: calculateZoom(DEFAULT_BBOX),
                                    pitch: 0,
                                    bearing: 0
                                });
                                setSelectedBbox(DEFAULT_BBOX);

                                // Reset manual bbox inputs
                                setManualBbox({
                                    west: DEFAULT_BBOX.west.toString(),
                                    south: DEFAULT_BBOX.south.toString(),
                                    east: DEFAULT_BBOX.east.toString(),
                                    north: DEFAULT_BBOX.north.toString()
                                });
                            }}
                        >
                            Reset View
                        </button>
                    </div>

                    {/* Manual coordinate inputs */}
                    <div className="manual-inputs">
                        <div className="input-section">
                            <h4>Manual Location Entry</h4>
                            <form onSubmit={handleManualLocationSubmit} className="coord-form">
                                <div className="input-group">
                                    <label>Longitude:</label>
                                    <input
                                        type="text"
                                        value={manualLon}
                                        onChange={(e) => setManualLon(e.target.value)}
                                        placeholder="-94.0"
                                    />
                                </div>
                                <div className="input-group">
                                    <label>Latitude:</label>
                                    <input
                                        type="text"
                                        value={manualLat}
                                        onChange={(e) => setManualLat(e.target.value)}
                                        placeholder="40.0"
                                    />
                                </div>
                                <button type="submit" className="submit-button">Set Location</button>
                            </form>
                        </div>

                        <div className="input-section">
                            <h4>Manual Bounding Box Entry</h4>
                            <form onSubmit={handleManualBboxSubmit} className="bbox-form">
                                <div className="bbox-inputs">
                                    <div className="input-group">
                                        <label>West:</label>
                                        <input
                                            type="text"
                                            value={manualBbox.west}
                                            onChange={(e) => setManualBbox({ ...manualBbox, west: e.target.value })}
                                            placeholder="-94.187"
                                        />
                                    </div>
                                    <div className="input-group">
                                        <label>South:</label>
                                        <input
                                            type="text"
                                            value={manualBbox.south}
                                            onChange={(e) => setManualBbox({ ...manualBbox, south: e.target.value })}
                                            placeholder="-39.020"
                                        />
                                    </div>
                                    <div className="input-group">
                                        <label>East:</label>
                                        <input
                                            type="text"
                                            value={manualBbox.east}
                                            onChange={(e) => setManualBbox({ ...manualBbox, east: e.target.value })}
                                            placeholder="37.062"
                                        />
                                    </div>
                                    <div className="input-group">
                                        <label>North:</label>
                                        <input
                                            type="text"
                                            value={manualBbox.north}
                                            onChange={(e) => setManualBbox({ ...manualBbox, north: e.target.value })}
                                            placeholder="18.229"
                                        />
                                    </div>
                                </div>
                                <button type="submit" className="submit-button">Set Bounding Box</button>
                            </form>
                        </div>
                    </div>

                    <div className="bbox-info">
                        <p>Current Bounding Box: {selectedBbox.west.toFixed(2)}, {selectedBbox.south.toFixed(2)}, {selectedBbox.east.toFixed(3)}, {selectedBbox.north.toFixed(3)}</p>
                        {currentLocation && (
                            <p>Selected Location: {currentLocation.longitude.toFixed(4)}, {currentLocation.latitude.toFixed(4)}</p>
                        )}
                    </div>

                    <div className="map-container" style={{ height: '400px' }}>
                        <DeckGL
                            viewState={viewState}
                            onViewStateChange={({ viewState }) => setViewState(viewState)}
                            controller={true}
                            layers={getLayers()}
                            getTooltip={({ object }) => object && object.date ?
                                `Date: ${formatDateStr(object.date)}\nWater Deficit: ${Math.round(object.def * 10) / 10} mm` : null}
                            onClick={handleMapClick}
                            getCursor={() => isSelectingLocation ? 'crosshair' : 'grab'}
                        >
                            <Map
                                mapStyle={config.map.defaultStyle}
                                mapboxAccessToken={config.map.mapboxToken}
                            />
                            {hoverInfo && hoverInfo.object && (
                                <div className="tooltip" style={{
                                    position: 'absolute',
                                    zIndex: 1,
                                    pointerEvents: 'none',
                                    left: hoverInfo.x,
                                    top: hoverInfo.y,
                                    backgroundColor: 'rgba(0,0,0,0.8)',
                                    color: 'white',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    fontSize: '12px'
                                }}>
                                    Date: {formatDateStr(hoverInfo.object.date)}<br />
                                    Water Deficit: {Math.round(hoverInfo.object.def * 10) / 10} mm
                                </div>
                            )}
                        </DeckGL>
                    </div>

                    <div className="debug-info">
                        <details open>
                            <summary>Debug Info</summary>
                            <p>Has Data: {processedData.length > 0 ? 'Yes' : 'No'}</p>
                            <p>Data Points: {processedData.length}</p>
                            {processedData.length > 0 && (
                                <div>
                                    <p>Sample Points (first 3):</p>
                                    <ul>
                                        {processedData.slice(0, 3).map((point, idx) => (
                                            <li key={idx}>
                                                Point {idx + 1}: Lon {point.lon.toFixed(6)}, Lat {point.lat.toFixed(6)}, Def {point.def.toFixed(2)}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            <p>Current Bounding Box:</p>
                            <ul>
                                <li>West: {selectedBbox.west}</li>
                                <li>South: {selectedBbox.south}</li>
                                <li>East: {selectedBbox.east}</li>
                                <li>North: {selectedBbox.north}</li>
                            </ul>
                            <p>Map Center: {viewState.longitude.toFixed(6)}, {viewState.latitude.toFixed(6)}</p>
                            <p>Map Zoom: {viewState.zoom.toFixed(2)}</p>
                            {currentLocation && (
                                <p>Selected Location: {currentLocation.longitude.toFixed(6)}, {currentLocation.latitude.toFixed(6)}</p>
                            )}
                            {debugInfo.error && (
                                <p className="error">Error: {debugInfo.error}</p>
                            )}
                        </details>
                    </div>

                    <div className="map-legend">
                        <h4>Water Deficit Scale</h4>
                        <div className="legend-items">
                            <div className="legend-item">
                                <div className="color-box" style={{ backgroundColor: 'rgb(49, 163, 84)' }}></div>
                                <span>0-20 mm (Low)</span>
                            </div>
                            <div className="legend-item">
                                <div className="color-box" style={{ backgroundColor: 'rgb(173, 221, 142)' }}></div>
                                <span>20-40 mm</span>
                            </div>
                            <div className="legend-item">
                                <div className="color-box" style={{ backgroundColor: 'rgb(247, 252, 185)' }}></div>
                                <span>40-60 mm</span>
                            </div>
                            <div className="legend-item">
                                <div className="color-box" style={{ backgroundColor: 'rgb(252, 146, 114)' }}></div>
                                <span>60-80 mm</span>
                            </div>
                            <div className="legend-item">
                                <div className="color-box" style={{ backgroundColor: 'rgb(222, 45, 38)' }}></div>
                                <span>gt 80 mm (Severe)</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="chart-section">
                    {renderTimeSeriesChart()}
                </div>
            </div>

            <footer className="dashboard-footer">
                <p>Data Source: TerraClim | Variable: Water Deficit (def)</p>
                <p>Default Bounding Box: {DEFAULT_BBOX.west}, {DEFAULT_BBOX.south}, {DEFAULT_BBOX.east}, {DEFAULT_BBOX.north}</p>
            </footer>

            <style jsx="true">{`
  .water-deficit-dashboard {
    font-family: Arial, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    box-sizing: border-box;
    color: #333;
  }
  .dashboard-header h1 {
    margin-bottom: 10px;
  }
  .location-info {
    color: #666;
    font-size: 14px;
    margin-bottom: 20px;
  }
  .location-info.warning {
    color: #e53935;
    font-weight: bold;
  }
  .dashboard-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-gap: 20px;
  }
  .map-section, .chart-section {
    grid-column: span 2;
    background: white;
    border-radius: 6px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    padding: 15px;
  }
  .map-container {
    border-radius: 4px;
    overflow: hidden;
    margin-top: 10px;
    position: relative;
  }
  .map-controls {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
  }
  .control-button {
    padding: 6px 12px;
    background-color: #4285f4;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .control-button:hover {
    background-color: #3367d6;
  }
  .control-button.active {
    background-color: #d23f31;
  }
  .bbox-info {
    font-size: 0.9em;
    color: #666;
    margin-bottom: 10px;
  }
  .debug-info {
    margin-top: 10px;
    font-size: 0.8em;
    color: #333;
    background-color: #f5f5f5;
    padding: 10px;
    border-radius: 4px;
  }
  .debug-info details {
    border: 1px solid #ddd;
    padding: 8px;
    background: #fff;
  }
    .queried-url {
    margin-top: 10px;
    margin-bottom: 10px;
}

.url-box {
    background-color: #f0f0f0;
    border: 1px solid #ddd;
    padding: 8px;
    font-family: monospace;
    font-size: 12px;
    word-break: break-all;
    border-radius: 4px;
    max-height: 60px;
    overflow-y: auto;
}
  .debug-info summary {
    cursor: pointer;
    font-weight: bold;
  }
  .debug-info ul {
    margin: 5px 0;
    padding-left: 20px;
  }
  .debug-info .error {
    color: #e53935;
  }
  .map-legend {
    margin-top: 10px;
    padding: 10px;
    border: 1px solid #ddd;
    background-color: rgba(255, 255, 255, 0.9);
    border-radius: 4px;
  }
  .legend-items {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 8px;
  }
  .legend-item {
    display: flex;
    align-items: center;
    font-size: 12px;
  }
  .color-box {
    width: 16px;
    height: 16px;
    margin-right: 5px;
    border: 1px solid #ddd;
  }
  .manual-inputs {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    margin-bottom: 15px;
    background-color: #f8f9fa;
    padding: 15px;
    border-radius: 6px;
    border: 1px solid #e0e0e0;
  }
  .input-section {
    flex: 1;
    min-width: 250px;
  }
  .input-section h4 {
    margin-top: 0;
    margin-bottom: 10px;
    color: #4285f4;
  }
  .coord-form, .bbox-form {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .input-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .input-group label {
    font-size: 14px;
    width: 80px;
    text-align: right;
    color: #555;
  }
  .input-group input {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
  }
  .bbox-inputs {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-bottom: 10px;
  }
  .submit-button {
    padding: 8px 12px;
    background-color: #4285f4;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: bold;
    align-self: flex-end;
  }
  .submit-button:hover {
    background-color: #3367d6;
  }
  .animation-controls {
    display: flex;
    align-items: center;
    margin-top: 15px;
    flex-wrap: wrap;
    gap: 10px;
  }
  .play-button {
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 15px;
    border-radius: 4px;
    cursor: pointer;
  }
  .play-button.playing {
    background: #f44336;
  }
  .current-time {
    margin: 0 10px;
    font-size: 14px;
  }
  input[type="range"] {
    flex-grow: 1;
    max-width: 300px;
  }
  .dashboard-footer {
    margin-top: 20px;
    text-align: center;
    color: #666;
    font-size: 12px;
    padding: 10px;
    border-top: 1px solid #eee;
  }
  .tooltip {
    z-index: 9;
  }
`}</style>
        </div>
    );
}
export default WaterDeficitDashboard;