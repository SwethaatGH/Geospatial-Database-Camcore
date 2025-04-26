// src/components/KeplerMapConfig.jsx
import React, { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { addDataToMap, toggleMapControl } from 'kepler.gl/actions';
import { getDataTypeConfig } from '../utils/dataProcessing';

/**
 * Component to configure Kepler.gl map based on data type
 */
const KeplerMapConfig = ({
    dataSource,
    variable,
    mapData,
    viewMode,
    isFirstLoad = false
}) => {
    const dispatch = useDispatch();

    // Apply specialized configuration for data types
    useEffect(() => {
        if (!mapData || !dataSource) return;

        // Get data-specific configurations
        const dataTypeConfig = getDataTypeConfig(dataSource, variable);

        // Create dataset object for Kepler
        const datasets = {
            info: {
                label: `${dataSource} - ${variable || 'Climate Data'}`,
                id: isFirstLoad ? 'climate-data' : `climate-data-${Date.now()}`
            },
            data: mapData
        };

        // Add data to the map with specialized configuration
        dispatch(
            addDataToMap({
                datasets,
                config: dataTypeConfig,
                options: {
                    centerMap: true,
                    readOnly: false
                }
            })
        );

        // Configure mapbox controls based on data type
        configureMapControls(dataSource, viewMode);
    }, [dataSource, variable, mapData, viewMode, dispatch, isFirstLoad]);

    /**
     * Configure Kepler.gl map controls based on data type
     */
    const configureMapControls = (dataSource, viewMode) => {
        // Show 3D visualization for elevation data
        if (dataSource === 'elev') {
            dispatch(toggleMapControl('visibleLayers', 'show'));
            dispatch(toggleMapControl('mapLegend', 'show'));
            dispatch(toggleMapControl('toggle3d', 'show'));
            dispatch(toggleMapControl('splitMaps', 'hide'));
        }
        // Show split view for temperature comparisons
        else if (dataSource === 'wc' && viewMode === 'bbox') {
            dispatch(toggleMapControl('visibleLayers', 'show'));
            dispatch(toggleMapControl('mapLegend', 'show'));
            dispatch(toggleMapControl('toggle3d', 'hide'));
            dispatch(toggleMapControl('splitMaps', 'show'));
        }
        // Default controls
        else {
            dispatch(toggleMapControl('visibleLayers', 'show'));
            dispatch(toggleMapControl('mapLegend', 'show'));
            dispatch(toggleMapControl('toggle3d', 'hide'));
            dispatch(toggleMapControl('splitMaps', 'hide'));
        }
    };

    // This is a configuration component, it doesn't render UI
    return null;
};

export default KeplerMapConfig;