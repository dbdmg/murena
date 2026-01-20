/**
 * StreetImage Component
 * 
 * Displays a street-level image from Mapillary API or falls back to a static OSM map.
 * Images are cached in localStorage to minimize API requests.
 */

import React, { useEffect, useState } from 'react';
import { Home, Loader2, MapPin } from 'lucide-react';

interface StreetImageProps {
    lat?: number;
    lng?: number;
    buildingId: string;
    className?: string;
}

interface CachedImage {
    url: string;
    type: 'mapillary' | 'static';
    timestamp: number;
}

const CACHE_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const MAPILLARY_ACCESS_TOKEN = 'MLY|9270576049682212|0cf744c2cfb0f0c4a8bfbfb41db80b37'; // Public demo token

/**
 * Get cached image from localStorage
 */
const getCachedImage = (buildingId: string): CachedImage | null => {
    try {
        const cached = localStorage.getItem(`street-image-${buildingId}`);
        if (!cached) return null;

        const parsed: CachedImage = JSON.parse(cached);

        // Check if cache is still valid
        if (Date.now() - parsed.timestamp > CACHE_DURATION_MS) {
            localStorage.removeItem(`street-image-${buildingId}`);
            return null;
        }

        return parsed;
    } catch {
        return null;
    }
};

/**
 * Save image URL to localStorage cache
 */
const setCachedImage = (buildingId: string, url: string, type: 'mapillary' | 'static') => {
    try {
        const cacheData: CachedImage = {
            url,
            type,
            timestamp: Date.now(),
        };
        localStorage.setItem(`street-image-${buildingId}`, JSON.stringify(cacheData));
    } catch {
        // Ignore storage errors (quota exceeded, etc.)
    }
};

/**
 * Build ESRI satellite image URL as fallback (shows actual buildings)
 */
const getStaticMapUrl = (lat: number, lng: number): string => {
    // Using ESRI World Imagery (satellite/aerial view)
    const zoom = 18;
    const x = Math.floor(((lng + 180) / 360) * Math.pow(2, zoom));
    const y = Math.floor(
        ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) *
        Math.pow(2, zoom)
    );
    return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${y}/${x}`;
};

/**
 * Fetch street image from Mapillary API
 */
const fetchMapillaryImage = async (lat: number, lng: number): Promise<string | null> => {
    try {
        // Create a small bounding box around the coordinates (roughly 50m)
        const delta = 0.0005; // ~50m at equator
        const bbox = `${lng - delta},${lat - delta},${lng + delta},${lat + delta}`;

        const response = await fetch(
            `https://graph.mapillary.com/images?access_token=${MAPILLARY_ACCESS_TOKEN}&fields=id,thumb_1024_url&bbox=${bbox}&limit=1`
        );

        if (!response.ok) return null;

        const data = await response.json();

        if (data.data && data.data.length > 0 && data.data[0].thumb_1024_url) {
            return data.data[0].thumb_1024_url;
        }

        return null;
    } catch {
        return null;
    }
};

export const StreetImage: React.FC<StreetImageProps> = ({ lat, lng, buildingId, className = '' }) => {
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [imageType, setImageType] = useState<'mapillary' | 'static' | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);

    useEffect(() => {
        const loadImage = async () => {
            // No coordinates available
            if (!lat || !lng) {
                setIsLoading(false);
                return;
            }

            // Check cache first
            const cached = getCachedImage(buildingId);
            if (cached) {
                setImageUrl(cached.url);
                setImageType(cached.type);
                setIsLoading(false);
                return;
            }

            // Try Mapillary
            setIsLoading(true);
            const mapillaryUrl = await fetchMapillaryImage(lat, lng);

            if (mapillaryUrl) {
                setImageUrl(mapillaryUrl);
                setImageType('mapillary');
                setCachedImage(buildingId, mapillaryUrl, 'mapillary');
            } else {
                // Fallback to static map
                const staticUrl = getStaticMapUrl(lat, lng);
                setImageUrl(staticUrl);
                setImageType('static');
                setCachedImage(buildingId, staticUrl, 'static');
            }

            setIsLoading(false);
        };

        loadImage();
    }, [lat, lng, buildingId]);

    // No coordinates - show placeholder
    if (!lat || !lng) {
        return (
            <div className={`bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center ${className}`}>
                <Home className="w-10 h-10 text-gray-600" />
            </div>
        );
    }

    // Loading state
    if (isLoading) {
        return (
            <div className={`bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center ${className}`}>
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
            </div>
        );
    }

    // Error or no image
    if (hasError || !imageUrl) {
        return (
            <div className={`bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center ${className}`}>
                <Home className="w-10 h-10 text-gray-600" />
            </div>
        );
    }

    return (
        <div className={`relative ${className}`}>
            <img
                src={imageUrl}
                alt="Street view"
                className="w-full h-full object-cover"
                onError={() => setHasError(true)}
            />
            {/* Image type indicator */}
            <div className="absolute bottom-1 right-1 flex items-center gap-1 bg-black/70 backdrop-blur-sm text-[9px] text-gray-200 px-1.5 py-0.5 rounded">
                <MapPin className="w-2.5 h-2.5" />
                {imageType === 'mapillary' ? 'Street View' : 'Satellite'}
            </div>
        </div>
    );
};
