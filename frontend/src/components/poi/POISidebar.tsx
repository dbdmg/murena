
import React from 'react';
import { X, ExternalLink, MapPin, Globe, Clock, Phone, Info } from 'lucide-react';
import type { POI } from '../../api/types';

interface POISidebarProps {
    poi: POI | null;
    onClose: () => void;
}

export const POISidebar: React.FC<POISidebarProps> = ({ poi, onClose }) => {
    if (!poi) return null;

    const details = poi.details || {};

    return (
        <div className="absolute top-0 left-0 h-full w-[400px] z-500 bg-[#0f1218]/95 backdrop-blur-xl border-r border-white/10 shadow-2xl transition-transform duration-300 ease-in-out transform translate-x-0">
            {/* Header Image Placeholder (Street View or Map Image could go here) */}
            <div className="relative h-48 bg-linear-to-b from-gray-800 to-gray-900 flex items-center justify-center overflow-hidden">
                <div className="absolute inset-0 bg-black/20" />
                <div className="text-6xl filter drop-shadow-2xl transform scale-150 opacity-90">{poi.icon}</div>

                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 bg-black/40 hover:bg-black/60 backdrop-blur-md rounded-full text-white/80 hover:text-white transition-all border border-white/10"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6 overflow-y-auto h-[calc(100%-12rem)]">

                {/* Header */}
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="bg-indigo-500/20 text-indigo-300 text-xs px-2 py-1 rounded-full border border-indigo-500/30 uppercase tracking-wider font-semibold">
                            {poi.category}
                        </span>
                        {details.operator && (
                            <span className="text-gray-500 text-xs bg-white/5 px-2 py-1 rounded-full border border-white/5">
                                {details.operator}
                            </span>
                        )}
                    </div>
                    <h2 className="text-2xl font-bold text-white leading-tight">{poi.name || 'Point of Interest'}</h2>
                </div>

                {/* Details List */}
                <div className="space-y-4">

                    {/* Address */}
                    {(details.address || details.city) && (
                        <div className="flex items-start gap-3 text-gray-300">
                            <MapPin className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                            <div>
                                <p className="text-sm">{details.address}</p>
                                <p className="text-sm text-gray-500">{details.city}</p>
                            </div>
                        </div>
                    )}

                    {/* Description */}
                    {details.description && (
                        <div className="flex items-start gap-3 text-gray-300">
                            <Info className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                            <p className="text-sm italic text-gray-400">{details.description}</p>
                        </div>
                    )}

                    {/* Opening Hours */}
                    {details.opening_hours && (
                        <div className="flex items-start gap-3 text-gray-300">
                            <Clock className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                            <p className="text-sm font-mono text-gray-400">{details.opening_hours}</p>
                        </div>
                    )}

                    {/* Website */}
                    {details.website && (
                        <div className="flex items-start gap-3">
                            <Globe className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                            <a
                                href={details.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-cyan-400 hover:text-cyan-300 hover:underline flex items-center gap-1 transition-colors break-all"
                            >
                                Visita sito web
                                <ExternalLink className="w-3 h-3" />
                            </a>
                        </div>
                    )}

                    {/* Phone */}
                    {details.phone && (
                        <div className="flex items-start gap-3 text-gray-300">
                            <Phone className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                            <p className="text-sm font-mono">{details.phone}</p>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
};
