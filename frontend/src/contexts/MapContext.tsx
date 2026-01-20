import React, { createContext, useContext, useState, type ReactNode } from 'react';

interface MapContextType {
    markersCount: number;
    totalCount: number;
    setMarkersCount: (count: number) => void;
    setTotalCount: (count: number) => void;
    isFiltered: boolean;
}

const MapContext = createContext<MapContextType | undefined>(undefined);

export const MapProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [markersCount, setMarkersCount] = useState(0);
    const [totalCount, setTotalCount] = useState(0);

    const isFiltered = markersCount !== totalCount && totalCount > 0;

    return (
        <MapContext.Provider value={{
            markersCount,
            totalCount,
            setMarkersCount,
            setTotalCount,
            isFiltered
        }}>
            {children}
        </MapContext.Provider>
    );
};

export const useMapContext = (): MapContextType => {
    const context = useContext(MapContext);
    if (!context) {
        // Return default values if not in provider (for non-map pages)
        return {
            markersCount: 0,
            totalCount: 0,
            setMarkersCount: () => { },
            setTotalCount: () => { },
            isFiltered: false,
        };
    }
    return context;
};
