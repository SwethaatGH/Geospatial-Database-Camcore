// src/utils/dataProcessing.js

import * as d3 from 'd3';

/**
 * Process API response data for visualization
 * @param {Object} data - API response data
 * @returns {Array} - Processed data for map visualization
 */
export const processData = (data) => {
    if (!data || !data.data || !data.data.length) {
        return [];
    }

    // Extract location
    const { lat, lon } = data.location;

    // Process time series data for visualization
    return data.data.map(item => {
        const values = item.values || {};
        const mainValue = Object.values(values)[0] || 0;

        return {
            lat,
            lon,
            date: item.date,
            year: item.year,
            month: item.month,
            day: item.day,
            value: mainValue,
            ...values
        };
    });
};

/**
 * Process bounding box data
 * @param {Object} data - API response for bbox
 * @returns {Array} - Processed data for map visualization
 */
export const processBboxData = (data) => {
    if (!data || !data.values || !data.values.length) {
        return [];
    }

    // Sample data if it's too large
    let processedValues = data.values;
    if (processedValues.length > 10000) {
        const samplingRate = Math.ceil(processedValues.length / 10000);
        processedValues = processedValues.filter((_, index) => index % samplingRate === 0);
    }

    // Process bbox data
    return processedValues.map(item => {
        // Handle data with var_name
        if (item.var_name) {
            return {
                lat: item.y,
                lon: item.x,
                date: item.date_id,
                variable: item.var_name,
                value: item.value
            };
        }

        // Handle data without var_name
        const valueFields = Object.keys(item).filter(
            key => !['x', 'y', 'date_id'].includes(key)
        );

        const mainValue = item[valueFields[0]] || 0;

        return {
            lat: item.y,
            lon: item.x,
            date: item.date_id,
            value: mainValue,
            ...valueFields.reduce((acc, key) => {
                acc[key] = item[key];
                return acc;
            }, {})
        };
    });
};

/**
 * Create a color scale based on data and data type
 * @param {Array} data - Processed data
 * @param {string} dataSource - Data source ID
 * @param {string} variable - Variable name
 * @returns {Function} - D3 color scale function
 */
export const createColorScale = (data, dataSource, variable) => {
    if (!data || !data.length) {
        return d3.scaleLinear().range(['#fff', '#000']);
    }

    // Extract values for scale
    const values = data.map(d => d.value).filter(v => v !== undefined && v !== null);
    const min = Math.min(...values);
    const max = Math.max(...values);

    // Water deficit (TerraClim def)
    if (dataSource === 'tc' && variable === 'def') {
        return d3.scaleLinear()
            .domain([0, 20, 40, 60, 80, 100])
            .range([
                '#31a354', // Low deficit
                '#addd8e',
                '#f7fcb9',
                '#ffffcc',
                '#fc9272',
                '#de2d26'  // High deficit
            ])
            .clamp(true);
    }

    // Precipitation
    if ((dataSource === 'wc' || dataSource === 'chirps') && variable === 'prec') {
        return d3.scaleLinear()
            .domain(d3.range(0, max, max / 8))
            .range([
                '#f7fbff',
                '#deebf7',
                '#c6dbef',
                '#9ecae1',
                '#6baed6',
                '#4292c6',
                '#2171b5',
                '#08519c'
            ])
            .clamp(true);
    }

    // Temperature max
    if (dataSource === 'wc' && variable === 'tmax') {
        return d3.scaleLinear()
            .domain([min, (min + max) / 2, max])
            .range(['#fee8c8', '#fc8d59', '#7f0000'])
            .clamp(true);
    }

    // Temperature min
    if (dataSource === 'wc' && variable === 'tmin') {
        return d3.scaleLinear()
            .domain([min, (min + max) / 2, max])
            .range(['#f7fbff', '#6baed6', '#08306b'])
            .clamp(true);
    }

    // SPEI drought index
    if (dataSource === 'spei') {
        return d3.scaleLinear()
            .domain([-2, -1, 0, 1, 2])
            .range(['#d73027', '#fdae61', '#ffffbf', '#abd9e9', '#4575b4'])
            .clamp(true);
    }

    // Default color scale
    return d3.scaleLinear()
        .domain([min, max])
        .range(['#f7fbff', '#08519c'])
        .clamp(true);
};

/**
 * Calculate statistics for time series data
 * @param {Array} data - Processed time series data
 * @param {string} variable - Variable name
 * @returns {Object} - Statistics
 */
export const calculateStats = (data, variable) => {
    if (!data || !data.length) {
        return {};
    }

    const values = data.map(d => d[variable]).filter(v => v !== undefined && v !== null);

    if (!values.length) {
        return {};
    }

    const sum = values.reduce((a, b) => a + b, 0);
    const average = sum / values.length;
    const max = Math.max(...values);
    const min = Math.min(...values);

    // Group by month
    const byMonth = {};
    data.forEach(d => {
        const month = d.month;
        if (!byMonth[month]) {
            byMonth[month] = [];
        }
        byMonth[month].push(d[variable]);
    });

    // Monthly averages
    const monthlyAverages = {};
    Object.keys(byMonth).forEach(month => {
        const monthValues = byMonth[month];
        monthlyAverages[month] = monthValues.reduce((a, b) => a + b, 0) / monthValues.length;
    });

    return {
        sum,
        average,
        max,
        min,
        monthlyAverages
    };
};

/**
 * Format data for time lapse visualization
 * @param {Array} data - Processed time series data
 * @param {number} steps - Number of frames for animation
 * @returns {Array} - Animation frames
 */
export const createTimeLapseFrames = (data, steps = 10) => {
    if (!data || !data.length) {
        return [];
    }

    // Sort by date
    const sortedData = [...data].sort((a, b) => new Date(a.date) - new Date(b.date));

    // If we have less data points than steps, use all data points
    if (sortedData.length <= steps) {
        return sortedData.map((item, index) => ({
            frame: index,
            date: item.date,
            data: [item]
        }));
    }

    // Create frames by sampling data points
    const frames = [];
    const step = Math.floor(sortedData.length / steps);

    for (let i = 0; i < steps; i++) {
        const index = i * step;
        if (index < sortedData.length) {
            frames.push({
                frame: i,
                date: sortedData[index].date,
                data: [sortedData[index]]
            });
        }
    }

    return frames;
};

/**
 * Sample large datasets to improve performance
 * @param {Array} data - Input data
 * @param {number} maxPoints - Maximum number of points
 * @returns {Array} - Sampled data
 */
export const sampleData = (data, maxPoints = 10000) => {
    if (!data || !data.length || data.length <= maxPoints) {
        return data;
    }

    const samplingRate = Math.ceil(data.length / maxPoints);
    return data.filter((_, index) => index % samplingRate === 0);
};

/**
 * Process time series data for charts
 * @param {Object} timeSeriesData - API response
 * @returns {Array} - Formatted data for charts
 */
export const processForCharts = (timeSeriesData) => {
    if (!timeSeriesData || !timeSeriesData.data || !timeSeriesData.data.length) {
        return [];
    }

    return timeSeriesData.data.map(item => {
        const values = item.values || {};

        return {
            date: item.date,
            year: item.year,
            month: item.month,
            day: item.day,
            ...values
        };
    });
};

/**
 * Format date string for display
 * @param {string} dateStr - ISO date string
 * @param {string} format - Output format ('month', 'day', or 'full')
 * @returns {string} - Formatted date string
 */
export const formatDate = (dateStr, format = 'full') => {
    const date = new Date(dateStr);

    switch (format) {
        case 'month':
            return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        case 'day':
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        case 'full':
        default:
            return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }
};

/**
 * Generate a specialized description based on data type
 * @param {string} dataSource - Data source ID
 * @param {string} variable - Variable name
 * @param {Object} stats - Statistics
 * @returns {string} - Description
 */
export const generateDescription = (dataSource, variable, stats) => {
    if (!stats) {
        return '';
    }

    // Water deficit (TerraClim def)
    if (dataSource === 'tc' && variable === 'def') {
        const criticalMonths = Object.values(stats.monthlyAverages).filter(v => v > 50).length;

        return `This location experiences an average water deficit of ${Math.round(stats.average)} mm. 
      The maximum deficit is ${Math.round(stats.max)} mm, with ${criticalMonths} month(s) showing critical deficit levels (>50mm).`;
    }

    // Precipitation
    if ((dataSource === 'wc' || dataSource === 'chirps') && variable === 'prec') {
        return `Total precipitation is ${Math.round(stats.sum)} mm, with an average of ${Math.round(stats.average)} mm per period. 
      The wettest period received ${Math.round(stats.max)} mm.`;
    }

    // Temperature
    if (dataSource === 'wc' && (variable === 'tmax' || variable === 'tmin')) {
        const tempType = variable === 'tmax' ? 'maximum' : 'minimum';

        return `The average ${tempType} temperature is ${stats.average.toFixed(1)}°C, ranging from 
      ${stats.min.toFixed(1)}°C to ${stats.max.toFixed(1)}°C across the time period.`;
    }

    // Default description
    return `Average value: ${stats.average.toFixed(2)}, Range: ${stats.min.toFixed(2)} to ${stats.max.toFixed(2)}`;
};



