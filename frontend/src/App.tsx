import { type ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { MapProvider } from './contexts/MapContext';
import { LoginPage } from './pages/LoginPage';
import { SearchPage } from './pages/SearchPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { MapPage } from './pages/MapPage';
import { SettingsPage } from './pages/SettingsPage';
import { HistoryPage } from './pages/HistoryPage';
import { AppLayout } from './components/layout/AppLayout';

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
                    <span className="text-gray-500 text-sm">Loading...</span>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <SettingsProvider>
                <AuthProvider>
                    <MapProvider>
                        <Router>
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
                        </Router>
                    </MapProvider>
                </AuthProvider>
            </SettingsProvider>
        </QueryClientProvider>
    );
}

export default App;

