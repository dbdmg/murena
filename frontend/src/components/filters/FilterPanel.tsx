import React, { useState, useEffect, useRef } from 'react';
import {
    Filter,
    X,
    Zap,
    Ruler,
    Calendar,
    RotateCcw,
    Check,
    ChevronDown,
    Building2,
    Activity,
    Shield,
    Layers,
    Sparkles,
    Target
} from 'lucide-react';

export interface FilterState {
    energyClasses: string[];
    minSurface: number | null;
    maxSurface: number | null;
    epocheCostruzione: string[];
    tipologiaBene: string[];
    utilizzo: string[];
    vincolo: string[];
    isMetaImmobile: boolean | null;
    naturaBene: string | null;
    hasApe: boolean | null;  // Filter for buildings with/without APE
    // Intelligence Map filters
    showOnlyTopPicks: boolean;
    showOnlyResults: boolean;
}

export const defaultFilters: FilterState = {
    energyClasses: [],
    minSurface: null,
    maxSurface: null,
    epocheCostruzione: [],
    tipologiaBene: [],
    utilizzo: [],
    vincolo: [],
    isMetaImmobile: null,
    naturaBene: null,
    hasApe: null,
    showOnlyTopPicks: false,
    showOnlyResults: false,
};

interface FilterPanelProps {
    filters: FilterState;
    onFiltersChange: (filters: FilterState) => void;
}

// Real values from db_metadata.json
const ENERGY_CLASSES = ['A1', 'A2', 'A4', 'B', 'C', 'D', 'E', 'F', 'G'];
const EPOCHE_COSTRUZIONE = [
    'Prima del 1919',
    'Dal 1919 al 1945',
    'Dal 1946 al 1960',
    'Dal 1961 al 1970',
    'Dal 1971 al 1980',
    'Dal 1981 al 1990',
    'Dal 1991 al 2000',
    'Dal 2001 al 2010',
    'Dopo il 2010',
];

const TIPOLOGIE_BENE = [
    'Abitazione',
    'Ufficio strutturato ed assimilabili',
    'Locale commerciale, negozio',
    'Magazzino e locali di deposito',
    'Fabbricato per attività produttiva (industriale, artigianale o agricola)',
    'Edificio scolastico',
    'Biblioteca, pinacoteca, museo, gallerie',
    'Ospedali, case di cura, cliniche e assimilabili',
    'Palazzo storico, castello',
    'Teatro, cinematografo',
    'Impianto sportivo',
    'Parcheggio collettivo',
];

const UTILIZZO_BENE = [
    'Utilizzato direttamente',
    'Non utilizzato',
    'In ristrutturazione/manutenzione',
    'Inutilizzabile',
];

const VINCOLI = [
    'Nessuno',
    'Dichiarazione di interesse culturale',
    'Dichiarazione di notevole interesse pubblico',
    'Verifica dell\'interesse culturale in corso',
];

const getEnergyClassColor = (cls: string, isSelected: boolean) => {
    if (!isSelected) return 'bg-white/5 text-gray-500 border-white/10 hover:border-white/30';
    const baseClass = cls.charAt(0);
    switch (baseClass) {
        case 'A': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
        case 'B': return 'bg-lime-500/20 text-lime-400 border-lime-500/50';
        case 'C': return 'bg-yellow-400/20 text-yellow-400 border-yellow-500/50';
        case 'D': return 'bg-orange-400/20 text-orange-400 border-orange-500/50';
        case 'E': return 'bg-orange-500/20 text-orange-500 border-orange-600/50';
        case 'F': return 'bg-red-500/20 text-red-400 border-red-500/50';
        case 'G': return 'bg-red-600/20 text-red-500 border-red-600/50';
        default: return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
    }
};

type ActiveDropdown = 'energy' | 'surface' | 'epoca' | 'tipologia' | 'utilizzo' | 'vincolo' | 'more' | null;

export const FilterPanel: React.FC<FilterPanelProps> = ({
    filters,
    onFiltersChange,
}) => {
    const [activeDropdown, setActiveDropdown] = useState<ActiveDropdown>(null);
    const [isExpanded, setIsExpanded] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    const activeFilterCount = [
        filters.energyClasses.length > 0,
        filters.minSurface !== null || filters.maxSurface !== null,
        filters.epocheCostruzione.length > 0,
        filters.tipologiaBene.length > 0,
        filters.utilizzo.length > 0,
        filters.vincolo.length > 0,
        filters.isMetaImmobile !== null,
        filters.naturaBene !== null,
        filters.hasApe !== null,
        filters.showOnlyTopPicks,
        filters.showOnlyResults,
    ].filter(Boolean).length;

    const hasActiveFilters = activeFilterCount > 0;

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                setActiveDropdown(null);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const toggleArrayFilter = (key: 'energyClasses' | 'epocheCostruzione' | 'tipologiaBene' | 'utilizzo' | 'vincolo', value: string) => {
        const current = filters[key] as string[];
        const newValues = current.includes(value)
            ? current.filter(v => v !== value)
            : [...current, value];
        onFiltersChange({ ...filters, [key]: newValues });
    };

    const handleReset = () => {
        onFiltersChange(defaultFilters);
        setActiveDropdown(null);
    };

    const getChipLabel = (type: ActiveDropdown): string => {
        switch (type) {
            case 'energy':
                return filters.energyClasses.length > 0
                    ? `Classe: ${filters.energyClasses.slice(0, 3).join(', ')}${filters.energyClasses.length > 3 ? '...' : ''}`
                    : 'Classe Energetica';
            case 'surface':
                if (filters.minSurface && filters.maxSurface) return `${filters.minSurface}-${filters.maxSurface}m²`;
                if (filters.minSurface) return `≥${filters.minSurface}m²`;
                if (filters.maxSurface) return `≤${filters.maxSurface}m²`;
                return 'Superficie';
            case 'epoca':
                return filters.epocheCostruzione.length > 0
                    ? `${filters.epocheCostruzione.length} periodi`
                    : 'Epoca';
            case 'tipologia':
                return filters.tipologiaBene.length > 0
                    ? `${filters.tipologiaBene.length} tipologie`
                    : 'Tipologia';
            case 'utilizzo':
                return filters.utilizzo.length > 0
                    ? `${filters.utilizzo.length} utilizzi`
                    : 'Utilizzo';
            case 'vincolo':
                return filters.vincolo.length > 0
                    ? `${filters.vincolo.length} vincoli`
                    : 'Vincolo';
            default:
                return '';
        }
    };

    const isChipActive = (type: ActiveDropdown): boolean => {
        switch (type) {
            case 'energy': return filters.energyClasses.length > 0;
            case 'surface': return filters.minSurface !== null || filters.maxSurface !== null;
            case 'epoca': return filters.epocheCostruzione.length > 0;
            case 'tipologia': return filters.tipologiaBene.length > 0;
            case 'utilizzo': return filters.utilizzo.length > 0;
            case 'vincolo': return filters.vincolo.length > 0;
            default: return false;
        }
    };

    const FilterChip: React.FC<{ type: ActiveDropdown; icon: React.ReactNode }> = ({ type, icon }) => {
        if (!type) return null;
        const isActive = isChipActive(type);
        const isOpen = activeDropdown === type;

        return (
            <button
                onClick={() => setActiveDropdown(isOpen ? null : type)}
                className={`
                    flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                    transition-all duration-200 border whitespace-nowrap
                    ${isActive
                        ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                        : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                    }
                    ${isOpen ? 'ring-1 ring-cyan-500/50' : ''}
                `}
            >
                {icon}
                <span>{getChipLabel(type)}</span>
                <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
        );
    };

    // Toggle Switch Component
    const ToggleSwitch: React.FC<{
        label: string;
        value: boolean | null;
        onChange: (val: boolean | null) => void;
        options?: { on: string; off: string };
    }> = ({ label, value, onChange, options = { on: 'Sì', off: 'No' } }) => (
        <div className="flex items-center justify-between gap-4 py-2">
            <span className="text-xs text-gray-400">{label}</span>
            <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
                <button
                    onClick={() => onChange(value === false ? null : false)}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${value === false
                        ? 'bg-red-500/20 text-red-400'
                        : 'text-gray-500 hover:text-gray-300'
                        }`}
                >
                    {options.off}
                </button>
                <button
                    onClick={() => onChange(null)}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${value === null
                        ? 'bg-gray-500/30 text-gray-300'
                        : 'text-gray-600 hover:text-gray-400'
                        }`}
                >
                    Tutti
                </button>
                <button
                    onClick={() => onChange(value === true ? null : true)}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${value === true
                        ? 'bg-cyan-500/20 text-cyan-400'
                        : 'text-gray-500 hover:text-gray-300'
                        }`}
                >
                    {options.on}
                </button>
            </div>
        </div>
    );

    return (
        <div ref={panelRef} className="relative">
            {/* Horizontal Filter Bar */}
            <div className={`
                bg-[#0a0d12]/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-xl shadow-black/30 p-2 
                flex items-center gap-2 transition-all duration-300 ease-in-out
                ${isExpanded ? 'pr-4' : ''}
            `}>
                {/* Filter Icon (like LayersPanel) */}
                <div className={`px-2 ${hasActiveFilters ? 'text-cyan-400' : 'text-gray-500'}`}>
                    <Filter className="w-4 h-4" />
                </div>

                {/* Main Filter Toggle Button (matches Livelli style) */}
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isExpanded || hasActiveFilters
                            ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                            : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                    `}
                >
                    <span className="font-medium">Filtri</span>
                    {activeFilterCount > 0 && (
                        <span className="ml-1 bg-cyan-500/30 px-1.5 py-0.5 rounded-full text-[10px]">
                            {activeFilterCount}
                        </span>
                    )}
                    <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </button>

                {/* Collapsible Chips Container */}
                <div className={`
                    flex items-center gap-2 overflow-hidden transition-all duration-500 ease-in-out
                    ${isExpanded ? 'opacity-100 max-w-[1000px]' : 'opacity-0 max-w-0'}
                `}>
                    <div className="w-px h-6 bg-white/10 mx-1 shrink-0" />

                    {/* Primary Filter Chips */}
                    <FilterChip type="energy" icon={<Zap className="w-3.5 h-3.5" />} />
                    <FilterChip type="surface" icon={<Ruler className="w-3.5 h-3.5" />} />
                    <FilterChip type="epoca" icon={<Calendar className="w-3.5 h-3.5" />} />
                    <FilterChip type="tipologia" icon={<Building2 className="w-3.5 h-3.5" />} />
                    <FilterChip type="utilizzo" icon={<Activity className="w-3.5 h-3.5" />} />
                    <FilterChip type="vincolo" icon={<Shield className="w-3.5 h-3.5" />} />

                    {/* More Filters & Agent Tuner */}
                    <button
                        onClick={() => setActiveDropdown(activeDropdown === 'more' ? null : 'more')}
                        className={`
                            flex items-center gap-1 px-2 py-2 rounded-lg text-xs
                            transition-all border whitespace-nowrap
                            ${(filters.isMetaImmobile !== null || filters.naturaBene !== null || filters.hasApe !== null || filters.showOnlyTopPicks || filters.showOnlyResults)
                                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                                : 'bg-white/5 text-gray-500 border-white/10 hover:border-white/20'
                            }
                            ${activeDropdown === 'more' ? 'ring-1 ring-cyan-500/50' : ''}
                        `}
                    >
                        <Layers className="w-3.5 h-3.5" />
                        <ChevronDown className={`w-3 h-3 transition-transform ${activeDropdown === 'more' ? 'rotate-180' : ''}`} />
                    </button>

                    <div className="w-px h-6 bg-white/10 mx-1 shrink-0" />

                    {/* Reset Button */}
                    {hasActiveFilters && (
                        <button
                            onClick={handleReset}
                            className="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-red-400 transition-colors whitespace-nowrap"
                            title="Reset filtri"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            Reset
                        </button>
                    )}
                </div>
            </div>

            {/* Dropdowns */}
            {activeDropdown && (
                <div className="absolute top-full left-0 mt-2 z-50">
                    <div className="bg-[#0a0d12]/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl shadow-black/50 p-4 max-h-[400px] overflow-y-auto">

                        {/* Energy Class Dropdown */}
                        {activeDropdown === 'energy' && (
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Zap className="w-4 h-4 text-yellow-400" />
                                        Classe Energetica
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="flex gap-2 flex-wrap">
                                    {ENERGY_CLASSES.map(cls => (
                                        <button
                                            key={cls}
                                            onClick={() => toggleArrayFilter('energyClasses', cls)}
                                            className={`
                                                px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                                                border flex items-center justify-center gap-1
                                                ${getEnergyClassColor(cls, filters.energyClasses.includes(cls))}
                                            `}
                                        >
                                            {filters.energyClasses.includes(cls) && <Check className="w-3 h-3" />}
                                            {cls}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Surface Dropdown */}
                        {activeDropdown === 'surface' && (
                            <div className="space-y-3 min-w-[260px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Ruler className="w-4 h-4 text-blue-400" />
                                        Superficie (m²)
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="flex gap-2 items-center">
                                    <input
                                        type="number"
                                        placeholder="Min"
                                        value={filters.minSurface ?? ''}
                                        onChange={e => onFiltersChange({
                                            ...filters,
                                            minSurface: e.target.value ? Number(e.target.value) : null
                                        })}
                                        className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:border-cyan-500/50 focus:outline-none"
                                    />
                                    <span className="text-gray-600">—</span>
                                    <input
                                        type="number"
                                        placeholder="Max"
                                        value={filters.maxSurface ?? ''}
                                        onChange={e => onFiltersChange({
                                            ...filters,
                                            maxSurface: e.target.value ? Number(e.target.value) : null
                                        })}
                                        className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:border-cyan-500/50 focus:outline-none"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Epoca Dropdown */}
                        {activeDropdown === 'epoca' && (
                            <div className="space-y-3 max-w-[320px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Calendar className="w-4 h-4 text-purple-400" />
                                        Epoca Costruzione
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                    {EPOCHE_COSTRUZIONE.map(epoca => (
                                        <button
                                            key={epoca}
                                            onClick={() => toggleArrayFilter('epocheCostruzione', epoca)}
                                            className={`
                                                px-2 py-1.5 rounded-lg text-[11px] transition-all
                                                border flex items-center gap-1 text-left
                                                ${filters.epocheCostruzione.includes(epoca)
                                                    ? 'bg-purple-500/20 text-purple-400 border-purple-500/50'
                                                    : 'bg-white/5 text-gray-500 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            {filters.epocheCostruzione.includes(epoca) && <Check className="w-3 h-3 shrink-0" />}
                                            <span className="truncate">{epoca}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Tipologia Dropdown */}
                        {activeDropdown === 'tipologia' && (
                            <div className="space-y-3 min-w-[300px] max-w-[400px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Building2 className="w-4 h-4 text-indigo-400" />
                                        Tipologia Bene
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="space-y-1 max-h-[250px] overflow-y-auto pr-2">
                                    {TIPOLOGIE_BENE.map(tipo => (
                                        <button
                                            key={tipo}
                                            onClick={() => toggleArrayFilter('tipologiaBene', tipo)}
                                            className={`
                                                w-full px-3 py-2 rounded-lg text-xs transition-all
                                                border flex items-center gap-2 text-left
                                                ${filters.tipologiaBene.includes(tipo)
                                                    ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/50'
                                                    : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${filters.tipologiaBene.includes(tipo)
                                                ? 'border-indigo-400 bg-indigo-500/30'
                                                : 'border-white/20'
                                                }`}>
                                                {filters.tipologiaBene.includes(tipo) && <Check className="w-3 h-3" />}
                                            </div>
                                            <span className="truncate">{tipo}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Utilizzo Dropdown */}
                        {activeDropdown === 'utilizzo' && (
                            <div className="space-y-3 min-w-[260px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Activity className="w-4 h-4 text-teal-400" />
                                        Utilizzo del Bene
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="space-y-1">
                                    {UTILIZZO_BENE.map(uso => (
                                        <button
                                            key={uso}
                                            onClick={() => toggleArrayFilter('utilizzo', uso)}
                                            className={`
                                                w-full px-3 py-2 rounded-lg text-xs transition-all
                                                border flex items-center gap-2 text-left
                                                ${filters.utilizzo.includes(uso)
                                                    ? 'bg-teal-500/20 text-teal-400 border-teal-500/50'
                                                    : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${filters.utilizzo.includes(uso)
                                                ? 'border-teal-400 bg-teal-500/30'
                                                : 'border-white/20'
                                                }`}>
                                                {filters.utilizzo.includes(uso) && <Check className="w-3 h-3" />}
                                            </div>
                                            <span>{uso}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Vincolo Dropdown */}
                        {activeDropdown === 'vincolo' && (
                            <div className="space-y-3 min-w-[280px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Shield className="w-4 h-4 text-amber-400" />
                                        Vincolo Culturale
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="space-y-1">
                                    {VINCOLI.map(vincolo => (
                                        <button
                                            key={vincolo}
                                            onClick={() => toggleArrayFilter('vincolo', vincolo)}
                                            className={`
                                                w-full px-3 py-2 rounded-lg text-xs transition-all
                                                border flex items-center gap-2 text-left
                                                ${filters.vincolo.includes(vincolo)
                                                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                                                    : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${filters.vincolo.includes(vincolo)
                                                ? 'border-amber-400 bg-amber-500/30'
                                                : 'border-white/20'
                                                }`}>
                                                {filters.vincolo.includes(vincolo) && <Check className="w-3 h-3" />}
                                            </div>
                                            <span className="truncate">{vincolo}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* More Filters Dropdown (Toggles) */}
                        {activeDropdown === 'more' && (
                            <div className="space-y-3 min-w-[280px]">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm text-gray-300">
                                        <Layers className="w-4 h-4 text-gray-400" />
                                        Altri Filtri
                                    </div>
                                    <button onClick={() => setActiveDropdown(null)} className="text-gray-500 hover:text-gray-300">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>

                                {/* Intelligence Map Filters */}
                                <div className="border-t border-white/10 pt-3">
                                    <div className="text-xs text-gray-400 mb-2 flex items-center gap-1.5">
                                        <Target className="w-3 h-3" />
                                        Visualizzazione Mappa
                                    </div>
                                    <div className="space-y-2">
                                        <button
                                            onClick={() => onFiltersChange({
                                                ...filters,
                                                showOnlyTopPicks: !filters.showOnlyTopPicks,
                                                showOnlyResults: filters.showOnlyTopPicks ? filters.showOnlyResults : false
                                            })}
                                            className={`
                                                w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all border
                                                ${filters.showOnlyTopPicks
                                                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                                                    : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            <Sparkles className="w-4 h-4" />
                                            <span>Solo Top Picks AI</span>
                                            {filters.showOnlyTopPicks && <Check className="w-3.5 h-3.5 ml-auto" />}
                                        </button>
                                        <button
                                            onClick={() => onFiltersChange({
                                                ...filters,
                                                showOnlyResults: !filters.showOnlyResults,
                                                showOnlyTopPicks: filters.showOnlyResults ? filters.showOnlyTopPicks : false
                                            })}
                                            className={`
                                                w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all border
                                                ${filters.showOnlyResults
                                                    ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                                                    : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                                }
                                            `}
                                        >
                                            <Target className="w-4 h-4" />
                                            <span>Solo Risultati Ricerca</span>
                                            {filters.showOnlyResults && <Check className="w-3.5 h-3.5 ml-auto" />}
                                        </button>
                                    </div>
                                </div>

                                <div className="border-t border-white/10 pt-3">
                                    <ToggleSwitch
                                        label="Meta Immobile"
                                        value={filters.isMetaImmobile}
                                        onChange={(val) => onFiltersChange({ ...filters, isMetaImmobile: val })}
                                        options={{ on: 'Solo Meta', off: 'Escludi' }}
                                    />
                                </div>

                                <div className="border-t border-white/10 pt-3">
                                    <ToggleSwitch
                                        label="Certificati APE"
                                        value={filters.hasApe}
                                        onChange={(val) => onFiltersChange({ ...filters, hasApe: val })}
                                        options={{ on: 'Con APE', off: 'Senza APE' }}
                                    />
                                </div>

                                <div className="border-t border-white/10 pt-3">
                                    <div className="text-xs text-gray-400 mb-2">Natura del Bene</div>
                                    <div className="flex gap-2">
                                        {['FABBRICATO', 'TERRENO'].map(natura => (
                                            <button
                                                key={natura}
                                                onClick={() => onFiltersChange({
                                                    ...filters,
                                                    naturaBene: filters.naturaBene === natura ? null : natura
                                                })}
                                                className={`
                                                    flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border
                                                    ${filters.naturaBene === natura
                                                        ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                                                        : 'bg-white/5 text-gray-500 border-white/10 hover:border-white/20'
                                                    }
                                                `}
                                            >
                                                {natura.charAt(0) + natura.slice(1).toLowerCase()}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
