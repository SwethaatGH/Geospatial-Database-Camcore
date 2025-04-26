// src/App.jsx
import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl';
// Import Mapbox CSS - this fixes the CSS error
import 'mapbox-gl/dist/mapbox-gl.css';
// Correct imports for deck.gl layers
import { ScatterplotLayer } from '@deck.gl/layers';
import { HeatmapLayer, GridLayer, ScreenGridLayer } from '@deck.gl/aggregation-layers';
// Custom components
import WaterDeficitDashboard from './specialized-views/WaterDeficitDashboard';
import { fetchTimeSeriesData } from './api/climateApi';
import { processData } from './utils/dataProcessing';
import config from './config';

const App = () => {
  const [dataSource, setDataSource] = useState('tc'); // Default to TerraClim
  const [variable, setVariable] = useState('def'); // Default to water deficit
  const [startDate, setStartDate] = useState(config.defaultDates.startDate);
  const [endDate, setEndDate] = useState(config.defaultDates.endDate);
  const [coordinates, setCoordinates] = useState({
    lat: config.defaultView.latitude,
    lon: config.defaultView.longitude
  });
  const [timeSeriesData, setTimeSeriesData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [viewState, setViewState] = useState({
    longitude: config.defaultView.longitude,
    latitude: config.defaultView.latitude,
    zoom: config.defaultView.zoom,
    pitch: 0,
    bearing: 0
  });

  // Load data when parameters change
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const data = await fetchTimeSeriesData({
          lat: coordinates.lat,
          lon: coordinates.lon,
          startDate,
          endDate,
          dataSource,
          variable
        });

        setTimeSeriesData(data);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [coordinates, startDate, endDate, dataSource, variable]);

  // Create layers based on data type
  const getLayers = () => {
    if (!timeSeriesData || !timeSeriesData.data || !timeSeriesData.data.length) {
      return [];
    }

    const processedData = processData(timeSeriesData);

    // Water deficit layer (TerraClim def)
    if (dataSource === 'tc' && variable === 'def') {
      return [
        new HeatmapLayer({
          id: 'water-deficit-heatmap',
          data: processedData,
          getPosition: d => [d.lon, d.lat],
          getWeight: d => d.def,
          radiusPixels: 60,
          colorRange: [
            [49, 163, 84, 255],   // Low deficit
            [173, 221, 142, 255],
            [247, 252, 185, 255],
            [252, 252, 204, 255],
            [252, 146, 114, 255],
            [222, 45, 38, 255]    // High deficit
          ]
        })
      ];
    }

    // Precipitation layer
    if ((dataSource === 'wc' || dataSource === 'chirps') && variable === 'prec') {
      return [
        new HeatmapLayer({
          id: 'precipitation-heatmap',
          data: processedData,
          getPosition: d => [d.lon, d.lat],
          getWeight: d => d.prec,
          radiusPixels: 60,
          colorRange: [
            [247, 251, 255, 255],
            [222, 235, 247, 255],
            [198, 219, 239, 255],
            [158, 202, 225, 255],
            [107, 174, 214, 255],
            [66, 146, 198, 255],
            [33, 113, 181, 255],
            [8, 81, 156, 255]
          ]
        })
      ];
    }

    // Temperature layer
    if (dataSource === 'wc' && (variable === 'tmax' || variable === 'tmin')) {
      const colorRange = variable === 'tmax' ?
        [
          [255, 255, 204, 255],
          [255, 237, 160, 255],
          [254, 217, 118, 255],
          [254, 178, 76, 255],
          [253, 141, 60, 255],
          [252, 78, 42, 255],
          [227, 26, 28, 255],
          [189, 0, 38, 255]
        ] :
        [
          [255, 255, 255, 255],
          [209, 229, 240, 255],
          [146, 197, 222, 255],
          [67, 147, 195, 255],
          [33, 102, 172, 255],
          [5, 48, 97, 255]
        ];

      return [
        new GridLayer({
          id: 'temperature-grid',
          data: processedData,
          getPosition: d => [d.lon, d.lat],
          getColorWeight: d => d[variable],
          cellSize: 5000,
          extruded: true,
          pickable: true,
          elevationScale: 50,
          getElevationWeight: d => d[variable],
          colorRange
        })
      ];
    }

    // Default layer
    return [
      new ScreenGridLayer({
        id: 'default-grid',
        data: processedData,
        getPosition: d => [d.lon, d.lat],
        getWeight: d => {
          const values = Object.values(d).filter(v => typeof v === 'number' && !isNaN(v));
          return values.length > 0 ? values[0] : 1;
        },
        cellSizePixels: 40,
        colorRange: [
          [0, 25, 0, 25],
          [0, 85, 0, 85],
          [0, 127, 0, 127],
          [0, 170, 0, 170],
          [0, 190, 0, 190],
          [0, 255, 0, 255]
        ]
      })
    ];
  };

  // Render specialized dashboard if available
  const renderDashboard = () => {
    if (isLoading) {
      return <div className="loading">Loading data...</div>;
    }

    if (dataSource === 'tc' && variable === 'def') {
      return <WaterDeficitDashboard timeSeriesData={timeSeriesData} />;
    }

    return (
      <div className="generic-dashboard">
        <div className="map-container">
          <DeckGL
            viewState={viewState}
            onViewStateChange={({ viewState }) => setViewState(viewState)}
            controller={true}
            layers={getLayers()}
          >
            <Map
              mapStyle={config.map.defaultStyle}
              mapboxAccessToken={config.map.mapboxToken}
            />
          </DeckGL>
        </div>
        <div className="info-panel">
          <h2>Climate Data Visualization</h2>
          <p>
            Source: {config.dataSources[dataSource]?.label || dataSource} | Variable: {variable}<br />
            Location: {coordinates.lat.toFixed(4)}, {coordinates.lon.toFixed(4)}<br />
            Period: {startDate} to {endDate}
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Climate Data Dashboard</h1>
        <div className="controls">
          <div className="control-group">
            <label>Data Source</label>
            <select value={dataSource} onChange={e => setDataSource(e.target.value)}>
              {Object.entries(config.dataSources).map(([key, source]) => (
                <option key={key} value={key}>{source.label}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Variable</label>
            <select value={variable} onChange={e => setVariable(e.target.value)}>
              {config.dataSources[dataSource]?.variables.map(v => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              disabled={['elev', 'sg'].includes(dataSource)}
            />
          </div>
          <div className="control-group">
            <label>End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              disabled={['elev', 'sg'].includes(dataSource)}
            />
          </div>
        </div>
      </header>
      <main className="app-content">
        {renderDashboard()}
      </main>
    </div>
  );
};

export default App;