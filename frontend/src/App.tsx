import { type ReactNode, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { MapProvider } from './contexts/MapContext';
import { AppLayout } from './components/layout/AppLayout';

// Lazy load pages
const LoginPage = lazy(() => import('./pages/LoginPage').then(module => ({ default: module.LoginPage })));
const SearchPage = lazy(() => import('./pages/SearchPage').then(module => ({ default: module.SearchPage })));
const ProcessingPage = lazy(() => import('./pages/ProcessingPage').then(module => ({ default: module.ProcessingPage })));
const MapPage = lazy(() => import('./pages/MapPage').then(module => ({ default: module.MapPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage').then(module => ({ default: module.HistoryPage })));

// Create Query Client
const queryClient = new QueryClient();

// Protected Route Component
const ProtectedRoute = ({ children }: { children: ReactNode }) => {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#0a0c10] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-gray-500 text-sm">Caricamento...</span>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};

// Global Loading Fallback
const PageLoader = () => (
    <div className="h-full w-full flex items-center justify-center bg-[#0a0c10]">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
    </div>
);

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <SettingsProvider>
                <AuthProvider>
                    <MapProvider>
                        <Router>
                            <Suspense fallback={<PageLoader />}>
                                <Routes>
                                    {/* Public Route */}
                                    <Route path="/login" element={<LoginPage />} />

                                    {/* Protected Routes */}
                                    <Route
                                        path="/"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <SearchPage />
                                                </AppLayout>
                                            </ProtectedRoute>
                                        }
                                    />
                                    <Route
                                        path="/processing/:runId"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <ProcessingPage />
                                                </AppLayout>
                                            </ProtectedRoute>
                                        }
                                    />
                                    <Route
                                        path="/map"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <MapPage />
                                                </AppLayout>
                                            </ProtectedRoute>
                                        }
                                    />
                                    <Route
                                        path="/settings"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <SettingsPage />
                                                </AppLayout>
                                            </ProtectedRoute>
                                        }
                                    />
                                    {/* Placeholder routes for future pages */}
                                    <Route
                                        path="/history"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <HistoryPage />
                                                </AppLayout>
                                            </ProtectedRoute>
                                        }
                                    />
                                </Routes>
                            </Suspense>
                        </Router>
                    </MapProvider>
                </AuthProvider>
            </SettingsProvider>
        </QueryClientProvider>
    );
}

export default App;

