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
import {
    LogOut,
    Home,
    Map as MapIcon,
    History,
    Settings,
    Info,
    Zap,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { AboutModal } from '../AboutModal';

interface AppLayoutProps {
    children: ReactNode;
}

// Navigation items - About is handled separately as it opens a modal
const navItems = [
    { label: 'Home', path: '/', icon: Home, description: 'Search & Command Center' },
    { label: 'Map', path: '/map', icon: MapIcon, description: 'Property Intelligence' },
    { label: 'History', path: '/history', icon: History, description: 'Past Analyses' },
    { label: 'Settings', path: '/settings', icon: Settings, description: 'Configuration' },
];

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
    const { logout, user } = useAuth();
    const location = useLocation();
    const [isExpanded, setIsExpanded] = useState(false);
    const [isAboutOpen, setIsAboutOpen] = useState(false);

    return (
        <div className="min-h-screen w-full relative bg-[#0a0c10] text-gray-200 overflow-hidden">
            {/* Ambient Background Effects */}
            <div className="fixed top-[-20%] left-[-10%] w-[600px] h-[600px] bg-blue-600/8 rounded-full blur-[150px] pointer-events-none z-0" />
            <div className="fixed bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px] pointer-events-none z-0" />
            <div className="fixed top-[40%] right-[20%] w-[300px] h-[300px] bg-purple-500/5 rounded-full blur-[100px] pointer-events-none z-0" />

            {/* Sidebar Navigation - Fixed position */}
            <motion.aside
                className="fixed left-0 top-0 h-screen z-20 flex flex-col border-r border-white/5 bg-[#0f1218]/80 backdrop-blur-xl"
                initial={false}
                animate={{ width: isExpanded ? 240 : 72 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                onMouseEnter={() => setIsExpanded(true)}
                onMouseLeave={() => setIsExpanded(false)}
            >
                {/* Logo Section */}
                <div className="p-4 border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-linear-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/30 shrink-0">
                            <Zap className="w-5 h-5 text-white" />
                        </div>
                        <AnimatePresence>
                            {isExpanded && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="overflow-hidden"
                                >
                                    <h1 className="font-bold text-sm text-white whitespace-nowrap">Command Center</h1>
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                        <span className="text-[10px] text-gray-500 whitespace-nowrap">System Online</span>
                                    </div>
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
                                        ? 'bg-linear-to-r from-blue-600/20 to-cyan-500/10 text-white shadow-lg shadow-blue-900/10 border border-white/5'
                                        : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                                    }
                                `}
                            >
                                {/* Active indicator - REMOVED for cleaner look per user request */}
                                {isActive && (
                                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-12 bg-cyan-400/50 blur-sm rounded-r-full" />
                                )}

                                <div className={`
                                    w-8 h-8 rounded-lg flex items-center justify-center shrink-0
                                    ${isActive
                                        ? 'bg-blue-500/20 text-cyan-400'
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

                                {/* Hover tooltip when collapsed */}
                                {!isExpanded && (
                                    <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-xs text-white rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                                        {item.label}
                                    </div>
                                )}
                            </Link>
                        );
                    })}
                </nav>

                {/* About Button - Opens Modal */}
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
                                    <span className="text-sm font-medium block whitespace-nowrap">About</span>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Hover tooltip when collapsed */}
                        {!isExpanded && (
                            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-xs text-white rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                                About
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
                                    <p className="text-[10px] text-gray-500">Administrator</p>
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
                                    title="Sign Out"
                                >
                                    <LogOut className="w-4 h-4" />
                                </motion.button>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </motion.aside>

            {/* Main Content Area - with left margin for fixed sidebar */}
            <main className="ml-[72px] relative z-10 overflow-auto h-screen">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={location.pathname}
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
