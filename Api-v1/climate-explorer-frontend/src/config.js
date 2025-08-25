// src/config.js

/**
 * Centralized configuration with environment variables
 * Compatible with Vite's import.meta.env
 */
const config = {
    // API configuration
    api: {
        baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    },

    // Map configuration
    map: {
        mapboxToken: import.meta.env.VITE_MAPBOX_TOKEN || '',
        defaultStyle: 'mapbox://styles/mapbox/light-v10',
    },

    // Default view settings
    defaultView: {
        latitude: parseFloat(import.meta.env.VITE_DEFAULT_LAT || '35.7796'),
        longitude: parseFloat(import.meta.env.VITE_DEFAULT_LON || '-78.6382'),
        zoom: parseFloat(import.meta.env.VITE_DEFAULT_ZOOM || '6'),
    },

    // Default time range
    defaultDates: {
        startDate: import.meta.env.VITE_DEFAULT_START_DATE || '2020-01-01',
        endDate: import.meta.env.VITE_DEFAULT_END_DATE || '2020-12-31',
    },

    // Data source configuration
    dataSources: {
        wc: {
            label: "WorldClim",
            variables: ["prec", "tmax", "tmin"]
        },
        spei: {
            label: "SPEI",
            variables: ["spei"]
        },
        chirps: {
            label: "CHIRPS",
            variables: ["prec"]
        },
        et: {
            label: "Evapotranspiration",
            variables: ["et"]
        },
        elev: {
            label: "Elevation",
            variables: ["elev"]
        },
        sg: {
            label: "SoilGrids",
            variables: ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"]
        },
        tc: {
            label: "TerraClim",
            variables: ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmin", "vap", "vpd", "ws"]
        },
        era5: {
            label: "ERA5",
            variables: ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3", "temp", "totprec", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"]
        }
    }
};

export default config;