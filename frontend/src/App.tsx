import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

import '@/styles/tokens.css';
import Layout from '@/components/layout/Layout';
import ErrorBoundary from '@/components/error/ErrorBoundary';

// Lazy load pages for code splitting
const HomePage = lazy(() => import('@/pages/Home'));
const SessionsPage = lazy(() => import('@/pages/Sessions'));
const GraphPage = lazy(() => import('@/pages/Graph'));
const EntitiesPage = lazy(() => import('@/pages/Entities'));

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
        <p className="text-gray-600 mt-2">Loading...</p>
      </div>
    </div>
  );
}

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Layout>
            <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/sessions" element={<SessionsPage />} />
                  <Route path="/graph" element={<GraphPage />} />
                  <Route path="/entities" element={<EntitiesPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </Layout>
        </Router>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;