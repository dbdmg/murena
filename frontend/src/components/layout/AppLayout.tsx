/**
 * AppLayout - Main layout with Command Center style sidebar
 *
 * New sidebar design with:
 * - Collapsed icon-only sidebar (expandable on hover)
 * - Navigation: Home, Map, History, Settings
 * - About button that opens modal
 * - User profile section at bottom
 * - Framer Motion animations
 */

import React, { useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';
import { useSettings } from '../../contexts/SettingsContext';
import { translations } from '../../utils/translations';
import {
    LogOut,
    Home,
    Map as MapIcon,
    History,
    Settings,
    Info,
    Languages,
    ScrollText,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { AboutModal } from '../AboutModal';
import murenaLogo40 from '../../assets/brand/MURENA_40x40px.svg';
import murenaWordmark from '../../assets/brand/MURENA_217x34px.svg';

interface AppLayoutProps {
    children: ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
    const { logout, user } = useAuth();
    const { language, setLanguage } = useSettings();
    const location = useLocation();
    const [isExpanded, setIsExpanded] = useState(false);
    const [isAboutOpen, setIsAboutOpen] = useState(false);

    const t = translations[language];

    // Navigation items
    const navItems = [
        { label: t.nav.home, path: '/', icon: Home },
        { label: t.nav.map, path: '/map', icon: MapIcon },
        { label: t.nav.history, path: '/history', icon: History },
        { label: t.nav.logs, path: '/logs', icon: ScrollText },
        { label: t.nav.settings, path: '/settings', icon: Settings },
    ];

    const toggleLanguage = () => {
        setLanguage(language === 'it' ? 'en' : 'it');
    };

    const currentLanguageLabel = language === 'it' ? 'Italiano (IT)' : 'English (EN)';
    const currentLanguageTooltip = language === 'it' ? 'Italiano' : 'English';
    const languageToggleTitle = language === 'it'
        ? 'Lingua corrente: Italiano. Switch to English'
        : 'Current language: English. Passa all\'Italiano';

    return (
        <div className="min-h-screen w-full relative bg-(--bg-main) text-(--text-primary) overflow-hidden tracking-tight">
            {/* Ambient Background Effects */}
            <div className="fixed top-[-20%] left-[-10%] w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[150px] pointer-events-none z-0" />
            <div className="fixed bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none z-0" />
            <div className="fixed top-[40%] right-[20%] w-[300px] h-[300px] bg-purple-500/5 rounded-full blur-[100px] pointer-events-none z-0" />

            {/* Sidebar Navigation - Fixed position */}
            <motion.aside
                className="fixed left-0 top-0 h-screen z-20 flex flex-col border-r border-(--border-light) bg-(--glass-bg) backdrop-blur-xl"
                initial={false}
                animate={{ width: isExpanded ? 240 : 72 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                onMouseEnter={() => setIsExpanded(true)}
                onMouseLeave={() => setIsExpanded(false)}
            >
                {/* Logo Section */}
                <div className="p-4 border-b border-white/5">
                    <div className="flex items-center justify-center min-h-[40px]">
                        <AnimatePresence mode="wait">
                            {isExpanded ? (
                                <motion.div
                                    key="wordmark"
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="overflow-hidden"
                                >
                                    <img src={murenaWordmark} alt="Murena" className="w-[138px] h-auto max-w-none" />
                                </motion.div>
                            ) : (
                                <motion.div
                                    key="symbol"
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.9 }}
                                    transition={{ duration: 0.15 }}
                                    className="w-10 h-10 flex items-center justify-center"
                                >
                                    <img src={murenaLogo40} alt="Murena" className="w-10 h-10" />
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="flex-1 p-3 space-y-1 overflow-hidden">
                    {navItems.map((item) => {
                        const isActive = location.pathname === item.path;
                        const Icon = item.icon;

                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`
                                    flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative
                                    ${isExpanded ? '' : 'justify-center'}
                                    ${isActive
                                        ? 'bg-linear-to-r from-emerald-600/20 to-green-500/10 text-white shadow-lg shadow-emerald-900/10 border border-white/5'
                                        : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                                    }
                                `}
                            >
                                {isActive && (
                                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-12 bg-emerald-400/50 blur-sm rounded-r-full" />
                                )}

                                <div className={`
                                    w-8 h-8 rounded-lg flex items-center justify-center shrink-0
                                    ${isActive
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'bg-white/5 text-gray-500 group-hover:text-gray-300 group-hover:bg-white/10'
                                    }
                                `}>
                                    <Icon className="w-4 h-4" />
                                </div>

                                <AnimatePresence>
                                    {isExpanded && (
                                        <motion.div
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: -10 }}
                                            transition={{ duration: 0.15 }}
                                            className="flex-1 overflow-hidden"
                                        >
                                            <span className="text-sm font-medium block whitespace-nowrap">{item.label}</span>
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                {!isExpanded && (
                                    <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-xs text-white rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                                        {item.label}
                                    </div>
                                )}
                            </Link>
                        );
                    })}
                </nav>

                {/* Language Switcher */}
                <div className="px-3 pb-2">
                    <button
                        onClick={toggleLanguage}
                        className={`
                            w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative text-gray-400 hover:text-white hover:bg-white/5
                            ${isExpanded ? '' : 'justify-center'}
                        `}
                        title={languageToggleTitle}
                    >
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-white/5 text-emerald-500/80 group-hover:text-emerald-400 group-hover:bg-emerald-500/10 transition-colors">
                            <Languages className="w-4 h-4" />
                        </div>

                        <AnimatePresence>
                            {isExpanded && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="flex-1 overflow-hidden text-left"
                                >
                                    <span className="text-sm font-medium block whitespace-nowrap">
                                        {currentLanguageLabel}
                                    </span>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {!isExpanded && (
                            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-xs text-white rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                                {currentLanguageTooltip}
                            </div>
                        )}
                    </button>
                </div>

                {/* About Button */}
                <div className="px-3 pb-2">
                    <button
                        onClick={() => setIsAboutOpen(true)}
                        className={`
                            w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative text-gray-400 hover:text-white hover:bg-white/5
                            ${isExpanded ? '' : 'justify-center'}
                        `}
                    >
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-white/5 text-gray-500 group-hover:text-gray-300 group-hover:bg-white/10">
                            <Info className="w-4 h-4" />
                        </div>

                        <AnimatePresence>
                            {isExpanded && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="flex-1 overflow-hidden text-left"
                                >
                                    <span className="text-sm font-medium block whitespace-nowrap">{t.nav.about}</span>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {!isExpanded && (
                            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-xs text-white rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                                {t.nav.about}
                            </div>
                        )}
                    </button>
                </div>

                {/* User Section */}
                <div className="p-3 border-t border-white/5">
                    <div className={`
                        flex items-center gap-3 p-2 rounded-xl bg-white/5 transition-all
                        ${isExpanded ? '' : 'justify-center'}
                    `}>
                        <div className="w-8 h-8 rounded-full bg-linear-to-tr from-orange-500 to-pink-500 flex items-center justify-center text-xs font-bold ring-2 ring-white/10 shrink-0">
                            {user?.username?.charAt(0).toUpperCase()}
                        </div>

                        <AnimatePresence>
                            {isExpanded && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="flex-1 min-w-0 overflow-hidden"
                                >
                                    <p className="text-sm font-medium text-white truncate">{user?.username}</p>
                                    <p className="text-[10px] text-gray-500">{t.nav.admin}</p>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <AnimatePresence>
                            {isExpanded && (
                                <motion.button
                                    initial={{ opacity: 0, scale: 0.8 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.8 }}
                                    transition={{ duration: 0.15 }}
                                    onClick={logout}
                                    className="p-1.5 rounded-lg hover:bg-red-500/20 hover:text-red-400 text-gray-500 transition-colors"
                                    title={t.nav.logout}
                                >
                                    <LogOut className="w-4 h-4" />
                                </motion.button>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </motion.aside>

            {/* Main Content Area */}
            <main className="ml-[72px] relative z-10 overflow-auto h-screen">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={location.pathname + language} // Add language to key to force re-render on switch
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ duration: 0.2 }}
                        className="h-full"
                    >
                        {children}
                    </motion.div>
                </AnimatePresence>
            </main>

            {/* About Modal */}
            <AboutModal isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />
        </div>
    );
};
