import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X,
    Sparkles,
    Brain,
    MapPin,
    Database,
    Cpu,
    Shield,
    Zap,
    Heart,
    ExternalLink,
    Github,
    Code2,
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface AboutModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface BentoCardProps {
    icon: React.ReactNode;
    title: string;
    description: string;
    iconBg: string;
    iconColor: string;
    delay?: number;
    size?: 'small' | 'medium' | 'large';
}

// ============================================================================
// Animation Variants
// ============================================================================

const overlayVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
};

const modalVariants = {
    hidden: { opacity: 0, scale: 0.95, y: 20 },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: {
            type: 'spring' as const,
            stiffness: 300,
            damping: 30,
            staggerChildren: 0.08,
            delayChildren: 0.1,
        },
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: 20,
        transition: { duration: 0.2 },
    },
};

const cardVariants = {
    hidden: { opacity: 0, y: 20, scale: 0.95 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: {
            type: 'spring' as const,
            stiffness: 400,
            damping: 25,
        },
    },
};

// ============================================================================
// Sub-components
// ============================================================================

const BentoCard: React.FC<BentoCardProps> = ({
    icon,
    title,
    description,
    iconBg,
    iconColor,
    size = 'small',
}) => {
    const sizeClasses = {
        small: '',
        medium: 'md:col-span-2',
        large: 'md:col-span-2 md:row-span-2',
    };

    return (
        <motion.div
            variants={cardVariants}
            className={`
                group relative p-4 bg-linear-to-br from-white/5 to-transparent
                border border-white/10 rounded-2xl backdrop-blur-sm
                hover:border-white/20 hover:from-white/8 transition-all duration-300
                ${sizeClasses[size]}
            `}
        >
            <div className={`inline-flex p-2.5 rounded-xl ${iconBg} mb-3`}>
                <span className={iconColor}>{icon}</span>
            </div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            <p className="text-xs text-gray-400 leading-relaxed">{description}</p>

            {/* Glow effect on hover */}
            <div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                <div className={`absolute inset-0 rounded-2xl ${iconBg} opacity-10 blur-xl`} />
            </div>
        </motion.div>
    );
};

const StatBadge: React.FC<{ label: string; value: string }> = ({ label, value }) => (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-full">
        <span className="text-xs text-gray-500">{label}</span>
        <span className="text-xs font-mono text-emerald-400">{value}</span>
    </div>
);

// ============================================================================
// Main Component
// ============================================================================

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose }) => {
    const [mounted, setMounted] = useState(false);

    if (isOpen && !mounted) {
        setMounted(true);
    }

    useEffect(() => {
        if (isOpen) {
            // Prevent body scroll when modal is open
            document.body.style.overflow = 'hidden';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isOpen]);

    // Handle ESC key
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        if (isOpen) window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [isOpen, onClose]);

    if (!mounted && !isOpen) return null;

    return (
        <AnimatePresence mode="wait" onExitComplete={() => setMounted(false)}>
            {isOpen && (
                <motion.div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    variants={overlayVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                >
                    {/* Backdrop */}
                    <motion.div
                        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    {/* Modal */}
                    <motion.div
                        className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-[#0f1117] border border-white/10 rounded-3xl shadow-2xl"
                        variants={modalVariants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                    >
                        {/* Close Button */}
                        <button
                            onClick={onClose}
                            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-xl transition-colors z-10"
                        >
                            <X className="w-5 h-5" />
                        </button>

                        {/* Content */}
                        <div className="p-6 md:p-8">
                            {/* Header */}
                            <motion.div variants={cardVariants} className="text-center mb-8">
                                {/* Logo */}
                                <div className="relative inline-flex mb-4">
                                    <div className="w-20 h-20 rounded-2xl bg-linear-to-br from-emerald-500 via-green-500 to-teal-600 flex items-center justify-center shadow-2xl shadow-emerald-500/30">
                                        <Brain className="w-10 h-10 text-white" />
                                    </div>
                                    {/* Sparkle decorations */}
                                    <Sparkles className="absolute -top-2 -right-2 w-5 h-5 text-amber-400" />
                                </div>

                                {/* Title */}
                                <h1 className="text-3xl font-bold mb-2">
                                    <span className="bg-linear-to-r from-emerald-400 via-green-400 to-teal-400 bg-clip-text text-transparent">
                                        Sistema Analitico Immobiliare
                                    </span>
                                </h1>
                                <p className="text-sm text-gray-400 mb-3">
                                    Mappa Intelligence per la Gestione del Patrimonio Immobiliare
                                </p>

                                {/* Version & Stats */}
                                <div className="flex flex-wrap items-center justify-center gap-2">
                                    <StatBadge label="Versione" value="0.9.2-alpha" />
                                    <StatBadge label="Build" value="2025.01" />
                                    <StatBadge label="Agenti" value="9 AI" />
                                </div>
                            </motion.div>

                            {/* Mission Statement */}
                            <motion.div
                                variants={cardVariants}
                                className="p-5 bg-linear-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/20 rounded-2xl mb-6"
                            >
                                <div className="flex items-start gap-3">
                                    <div className="p-2 bg-emerald-500/20 rounded-xl">
                                        <Zap className="w-5 h-5 text-emerald-400" />
                                    </div>
                                    <div>
                                        <h2 className="text-sm font-semibold text-emerald-300 mb-1">La nostra missione</h2>
                                        <p className="text-sm text-gray-400 leading-relaxed">
                                            Trasformiamo la gestione del patrimonio immobiliare pubblico attraverso
                                            l'intelligenza artificiale, rendendo l'analisi dei dati accessibile,
                                            veloce e azionabile per decisori e analisti.
                                        </p>
                                    </div>
                                </div>
                            </motion.div>

                            {/* Bento Grid */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                                <BentoCard
                                    icon={<Brain className="w-4 h-4" />}
                                    title="Multi-Agent AI"
                                    description="5 agenti specializzati orchestrati per analisi complesse"
                                    iconBg="bg-violet-500/20"
                                    iconColor="text-violet-400"
                                />
                                <BentoCard
                                    icon={<MapPin className="w-4 h-4" />}
                                    title="Geospatial"
                                    description="Visualizzazione interattiva su mappa con clustering"
                                    iconBg="bg-emerald-500/20"
                                    iconColor="text-emerald-400"
                                />
                                <BentoCard
                                    icon={<Database className="w-4 h-4" />}
                                    title="25K+ Immobili"
                                    description="Dataset completo del patrimonio pubblico"
                                    iconBg="bg-emerald-500/20"
                                    iconColor="text-emerald-400"
                                />
                                <BentoCard
                                    icon={<Cpu className="w-4 h-4" />}
                                    title="Real-time"
                                    description="Analisi e scoring in tempo reale"
                                    iconBg="bg-amber-500/20"
                                    iconColor="text-amber-400"
                                />
                            </div>

                            {/* Tech Stack */}
                            <motion.div variants={cardVariants} className="mb-6">
                                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <Code2 className="w-3.5 h-3.5" />
                                    Tech Stack
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                    {[
                                        { name: 'React', color: 'text-emerald-400 bg-emerald-500/10' },
                                        { name: 'TypeScript', color: 'text-emerald-400 bg-emerald-500/10' },
                                        { name: 'FastAPI', color: 'text-emerald-400 bg-emerald-500/10' },
                                        { name: 'LangChain', color: 'text-violet-400 bg-violet-500/10' },
                                        { name: 'Gemini', color: 'text-emerald-400 bg-emerald-500/10' },
                                        { name: 'MapLibre', color: 'text-amber-400 bg-amber-500/10' },
                                        { name: 'Tailwind', color: 'text-emerald-400 bg-emerald-500/10' },
                                        { name: 'PostgreSQL', color: 'text-emerald-400 bg-emerald-500/10' },
                                    ].map((tech) => (
                                        <span
                                            key={tech.name}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-lg border border-white/5 ${tech.color}`}
                                        >
                                            {tech.name}
                                        </span>
                                    ))}
                                </div>
                            </motion.div>

                            {/* Footer */}
                            <motion.div
                                variants={cardVariants}
                                className="pt-5 border-t border-white/10"
                            >
                                <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                                    {/* Credits */}
                                    <div className="flex items-center gap-2 text-xs text-gray-500">
                                        <span>Made with</span>
                                        <Heart className="w-3 h-3 text-red-400" />
                                        <span>for MEF</span>
                                    </div>

                                    {/* Links */}
                                    <div className="flex items-center gap-3">
                                        <a
                                            href="https://github.com"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
                                        >
                                            <Github className="w-3.5 h-3.5" />
                                            Source
                                        </a>
                                        <a
                                            href="#"
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
                                        >
                                            <Shield className="w-3.5 h-3.5" />
                                            Privacy
                                        </a>
                                        <a
                                            href="#"
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
                                        >
                                            <ExternalLink className="w-3.5 h-3.5" />
                                            Docs
                                        </a>
                                    </div>
                                </div>

                                {/* Copyright */}
                                <p className="text-center text-[10px] text-gray-600 mt-4">
                                    © 2025 ResPublica AI • All rights reserved • MEF - Ministero dell'Economia e delle Finanze
                                </p>
                            </motion.div>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default AboutModal;
