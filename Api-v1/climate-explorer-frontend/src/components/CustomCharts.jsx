// src/components/CustomCharts.jsx
import React, { useMemo } from 'react';
import {
    LineChart, Line, BarChart, Bar, AreaChart, Area,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { processTimeSeriesForCharts } from '../utils/dataProcessing';

const CustomCharts = ({ dataSource, variable, timeSeriesData, viewMode }) => {
    // Process data for charts
    const chartData = useMemo(() => {
        if (!timeSeriesData) return [];
        return processTimeSeriesForCharts(timeSeriesData, variable);
    }, [timeSeriesData, variable]);

    // Get chart configuration based on data source and variable
    const getChartConfig = () => {
        // For TerraClim water deficit (def)
        if (dataSource === 'tc' && variable === 'def') {
            return {
                type: 'bar',
                color: '#de2d26',
                label: 'Water Deficit',
                unit: 'mm',
                description: 'Water deficit represents the difference between potential and actual evapotranspiration.'
            };
        }

        // For precipitation
        if ((dataSource === 'wc' || dataSource === 'chirps') && variable === 'prec') {
            return {
                type: 'bar',
                color: '#2171b5',
                label: 'Precipitation',
                unit: 'mm',
                description: 'Total precipitation amount.'
            };
        }

        // For temperature
        if (dataSource === 'wc' && (variable === 'tmax' || variable === 'tmin')) {
            return {
                type: 'line',
                color: variable === 'tmax' ? '#d7301f' : '#225ea8',
                label: variable === 'tmax' ? 'Maximum Temperature' : 'Minimum Temperature',
                unit: '°C',
                description: variable === 'tmax' ? 'Maximum daily temperature.' : 'Minimum daily temperature.'
            };
        }

        // For SPEI (standardized precipitation-evapotranspiration index)
        if (dataSource === 'spei') {
            return {
                type: 'area',
                color: '#74add1',
                label: 'SPEI',
                unit: '',
                description: 'Values above 0 indicate wet conditions, below 0 indicate drought conditions.'
            };
        }

        // Default chart config
        return {
            type: 'line',
            color: '#6baed6',
            label: variable || 'Value',
            unit: '',
            description: ''
        };
    };

    const config = getChartConfig();

    // If no data is available
    if (!chartData.length) {
        return (
            <div className="no-data-message">
                <h3>No data available</h3>
                <p>Select a location and time range to view data</p>
            </div>
        );
    }

    // Get all variables in the data
    const dataVariables = Object.keys(chartData[0]).filter(
        key => !['date', 'dateStr'].includes(key)
    );

    // Determine x-axis date format based on data cadence
    const hasDay = chartData[0].hasOwnProperty('day');
    const dateFormat = hasDay ? 'MM/DD/YYYY' : 'MM/YYYY';

    // Render the appropriate chart based on configuration
    const renderChart = () => {
        switch (config.type) {
            case 'bar':
                return (
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="dateStr"
                                label={{ value: 'Date', position: 'insideBottomRight', offset: -10 }}
                            />
                            <YAxis
                                label={{ value: `${config.label} (${config.unit})`, angle: -90, position: 'insideLeft' }}
                            />
                            <Tooltip formatter={(value) => [`${value} ${config.unit}`, config.label]} />
                            <Legend />
                            {dataVariables.map((varName, index) => (
                                <Bar
                                    key={varName}
                                    dataKey={varName}
                                    name={varName}
                                    fill={config.color}
                                    opacity={dataVariables.length > 1 ? 0.7 - (index * 0.1) : 0.7}
                                />
                            ))}
                        </BarChart>
                    </ResponsiveContainer>
                );

            case 'area':
                return (
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="dateStr"
                                label={{ value: 'Date', position: 'insideBottomRight', offset: -10 }}
                            />
                            <YAxis
                                label={{ value: `${config.label} (${config.unit})`, angle: -90, position: 'insideLeft' }}
                            />
                            <Tooltip formatter={(value) => [`${value} ${config.unit}`, config.label]} />
                            <Legend />
                            {dataVariables.map((varName, index) => (
                                <Area
                                    key={varName}
                                    type="monotone"
                                    dataKey={varName}
                                    name={varName}
                                    stroke={config.color}
                                    fill={config.color}
                                    opacity={dataVariables.length > 1 ? 0.7 - (index * 0.1) : 0.7}
                                />
                            ))}
                        </AreaChart>
                    </ResponsiveContainer>
                );

            case 'line':
            default:
                return (
                    <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="dateStr"
                                label={{ value: 'Date', position: 'insideBottomRight', offset: -10 }}
                            />
                            <YAxis
                                label={{ value: `${config.label} (${config.unit})`, angle: -90, position: 'insideLeft' }}
                            />
                            <Tooltip formatter={(value) => [`${value} ${config.unit}`, config.label]} />
                            <Legend />
                            {dataVariables.map((varName, index) => (
                                <Line
                                    key={varName}
                                    type="monotone"
                                    dataKey={varName}
                                    name={varName}
                                    stroke={
                                        dataVariables.length > 1 && index === 1 ? '#d7301f' : config.color
                                    }
                                    dot={{ r: 3 }}
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                );
        }
    };

    // Render time series chart for specific data types
    const renderTimeSeriesVisualization = () => {
        // Special visualization for TerraClim water deficit over time
        if (dataSource === 'tc' && variable === 'def') {
            return (
                <div className="specialized-chart water-deficit-chart">
                    <h3>Water Deficit Time Series</h3>
                    {renderChart()}
                    <p className="chart-description">
                        {config.description}
                        Higher values indicate more severe water deficit conditions.
                    </p>

                    {/* Water deficit metrics */}
                    <div className="metrics-panel">
                        <h4>Key Metrics</h4>
                        <div className="metrics-grid">
                            <div className="metric">
                                <span className="metric-label">Average Deficit:</span>
                                <span className="metric-value">
                                    {Math.round(chartData.reduce((sum, item) => sum + item.def, 0) / chartData.length * 10) / 10} mm
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Maximum Deficit:</span>
                                <span className="metric-value">
                                    {Math.round(Math.max(...chartData.map(item => item.def)) * 10) / 10} mm
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Months gt 50mm:</span>
                                <span className="metric-value">
                                    {chartData.filter(item => item.def > 50).length}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // Special visualization for precipitation data
        if ((dataSource === 'wc' || dataSource === 'chirps') && variable === 'prec') {
            return (
                <div className="specialized-chart precipitation-chart">
                    <h3>Precipitation Time Series</h3>
                    {renderChart()}
                    <p className="chart-description">
                        {config.description}
                        The chart shows the distribution of precipitation over time.
                    </p>

                    {/* Precipitation metrics */}
                    <div className="metrics-panel">
                        <h4>Key Metrics</h4>
                        <div className="metrics-grid">
                            <div className="metric">
                                <span className="metric-label">Total Precipitation:</span>
                                <span className="metric-value">
                                    {Math.round(chartData.reduce((sum, item) => sum + item.prec, 0))} mm
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Average Monthly:</span>
                                <span className="metric-value">
                                    {Math.round(chartData.reduce((sum, item) => sum + item.prec, 0) / chartData.length)} mm
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Maximum:</span>
                                <span className="metric-value">
                                    {Math.round(Math.max(...chartData.map(item => item.prec)))} mm
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // Temperature visualization with min/max comparison if both are available
        if (dataSource === 'wc' && (variable === 'tmax' || variable === 'tmin')) {
            const hasBothTemps = dataVariables.includes('tmax') && dataVariables.includes('tmin');

            return (
                <div className="specialized-chart temperature-chart">
                    <h3>Temperature Time Series</h3>
                    {renderChart()}
                    <p className="chart-description">
                        {config.description}
                        {hasBothTemps ? ' The chart shows both maximum and minimum temperatures.' : ''}
                    </p>

                    {/* Temperature metrics */}
                    <div className="metrics-panel">
                        <h4>Key Metrics</h4>
                        <div className="metrics-grid">
                            {variable === 'tmax' && (
                                <>
                                    <div className="metric">
                                        <span className="metric-label">Average Max Temp:</span>
                                        <span className="metric-value">
                                            {Math.round(chartData.reduce((sum, item) => sum + item.tmax, 0) / chartData.length * 10) / 10}°C
                                        </span>
                                    </div>
                                    <div className="metric">
                                        <span className="metric-label">Highest Max Temp:</span>
                                        <span className="metric-value">
                                            {Math.round(Math.max(...chartData.map(item => item.tmax)) * 10) / 10}°C
                                        </span>
                                    </div>
                                </>
                            )}

                            {variable === 'tmin' && (
                                <>
                                    <div className="metric">
                                        <span className="metric-label">Average Min Temp:</span>
                                        <span className="metric-value">
                                            {Math.round(chartData.reduce((sum, item) => sum + item.tmin, 0) / chartData.length * 10) / 10}°C
                                        </span>
                                    </div>
                                    <div className="metric">
                                        <span className="metric-label">Lowest Min Temp:</span>
                                        <span className="metric-value">
                                            {Math.round(Math.min(...chartData.map(item => item.tmin)) * 10) / 10}°C
                                        </span>
                                    </div>
                                </>
                            )}

                            {hasBothTemps && (
                                <div className="metric">
                                    <span className="metric-label">Avg Temp Range:</span>
                                    <span className="metric-value">
                                        {Math.round(chartData.reduce((sum, item) =>
                                            sum + (item.tmax - item.tmin), 0) / chartData.length * 10) / 10}°C
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            );
        }

        // SPEI drought index visualization
        if (dataSource === 'spei') {
            const droughtCount = chartData.filter(item => item.spei < -1).length;
            const wetCount = chartData.filter(item => item.spei > 1).length;
            const normalCount = chartData.length - droughtCount - wetCount;

            return (
                <div className="specialized-chart spei-chart">
                    <h3>SPEI Drought Index</h3>
                    {renderChart()}
                    <p className="chart-description">
                        SPEI (Standardized Precipitation-Evapotranspiration Index) measures drought intensity.
                        Values below -1 indicate drought conditions, above 1 indicate abnormally wet conditions.
                    </p>

                    {/* SPEI metrics */}
                    <div className="metrics-panel">
                        <h4>Drought Analysis</h4>
                        <div className="metrics-grid">
                            <div className="metric">
                                <span className="metric-label">Drought Months:</span>
                                <span className="metric-value">
                                    {droughtCount} ({Math.round(droughtCount / chartData.length * 100)}%)
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Normal Months:</span>
                                <span className="metric-value">
                                    {normalCount} ({Math.round(normalCount / chartData.length * 100)}%)
                                </span>
                            </div>
                            <div className="metric">
                                <span className="metric-label">Wet Months:</span>
                                <span className="metric-value">
                                    {wetCount} ({Math.round(wetCount / chartData.length * 100)}%)
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // Default visualization
        return (
            <div className="default-chart">
                <h3>{variable || 'Data'} Time Series</h3>
                {renderChart()}
                <p className="chart-description">
                    {config.description || `Time series data for ${variable || 'selected variable'}.`}
                </p>
            </div>
        );
    };

    // For point time series data
    if (viewMode === 'point') {
        return renderTimeSeriesVisualization();
    }

    // For bbox data (multiple points)
    return (
        <div className="bbox-data-visualization">
            <h3>Area Data Visualization</h3>
            <p>
                Selected area contains a large number of data points.
                Kepler.gl map visualization is best for spatial patterns.
            </p>

            <div className="data-stats">
                <h4>Data Statistics</h4>
                <p>The selected area contains data that can be viewed on the map.</p>
                <p>Use Kepler.gl controls to adjust visualization settings.</p>
            </div>
        </div>
    );
};

export default CustomCharts;