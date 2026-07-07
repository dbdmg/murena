import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { MapProvider } from './contexts/MapContext';
import { AppLayout } from './components/layout/AppLayout';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { PageLoader } from './components/common/PageLoader';

// Lazy load pages
const LoginPage = lazy(() => import('./pages/LoginPage').then(module => ({ default: module.LoginPage })));
const SearchPage = lazy(() => import('./pages/SearchPage').then(module => ({ default: module.SearchPage })));
const ProcessingPage = lazy(() => import('./pages/ProcessingPage').then(module => ({ default: module.ProcessingPage })));
const MapPage = lazy(() => import('./pages/MapPage').then(module => ({ default: module.MapPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage').then(module => ({ default: module.HistoryPage })));
const LogsPage = lazy(() => import('./pages/LogsPage').then(module => ({ default: module.LogsPage })));

// Create Query Client
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 5 * 60 * 1000, // 5 minutes
        },
    },
});

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
                                    <Route
                                        path="/logs"
                                        element={
                                            <ProtectedRoute>
                                                <AppLayout>
                                                    <LogsPage />
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

