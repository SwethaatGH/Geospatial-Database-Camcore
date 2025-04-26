// src/api/climateApi.js

// Get API base URL from environment variables
const API_BASE_URL = 'http://localhost:8000';


/**
 * Fetches time series data for a specific point
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} - API response
 */
export const fetchTimeSeriesData = async ({
    lat,
    lon,
    startDate,
    endDate,
    dataSource,
    variable
}) => {
    try {
        // Construct the API URL
        const apiUrl = new URL(`http://localhost:8000/climate-data-timeseries/`);

        // Add query parameters
        apiUrl.searchParams.append('lat', lat);
        apiUrl.searchParams.append('lon', lon);

    

        // Only add dates for non-static data sources
        if (!['elev', 'sg'].includes(dataSource)) {
            apiUrl.searchParams.append('start_date', startDate);
            apiUrl.searchParams.append('end_date', endDate);
        }

        // Add data source
        apiUrl.searchParams.append('data_source', dataSource);

        // Add variable if specified (for soil grids)
        if (dataSource === 'sg' && variable) {
            apiUrl.searchParams.append('variable', variable);
        }

        console.log(`Fetching data from: ${apiUrl.toString()}`);

        // Make the API request
        const response = await fetch(apiUrl.toString());

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        // Parse response
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching time series data:', error);
        throw error;
    }
};

/**
 * Fetches data for a bounding box area
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} - API response
 */
export const fetchBboxData = async ({
    minLat,
    minLon,
    maxLat,
    maxLon,
    startDate,
    endDate,
    dataSource,
    variable
}) => {
    try {
        // Construct the API URL
        const apiUrl = new URL("http://localhost:8000/climate-data-timeseries-bbox/");

        // Add query parameters
        apiUrl.searchParams.append('min_lat', minLat);
        apiUrl.searchParams.append('min_lon', minLon);
        apiUrl.searchParams.append('max_lat', maxLat);
        apiUrl.searchParams.append('max_lon', maxLon);

        // Only add dates for non-static data sources
        if (!['elev', 'sg'].includes(dataSource)) {
            apiUrl.searchParams.append('start_date', startDate);
            apiUrl.searchParams.append('end_date', endDate);
        }

        // Add data source
        apiUrl.searchParams.append('data_source', dataSource);

        console.log(`Fetching bbox data from: ${apiUrl.toString()}`);

        // Make the API request
        const response = await fetch(apiUrl.toString());

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        // Check if response is too large (> 10MB)
        const contentLength = response.headers.get('content-length');
        if (contentLength && parseInt(contentLength, 10) > 10 * 1024 * 1024) {
            throw new Error('Response too large. Please select a smaller area or shorter time period.');
        }

        // Parse response
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching bbox data:', error);
        throw error;
    }
};