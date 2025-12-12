import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  FileText,
  Network,
  Database,
  Menu,
  X,
  Wifi,
  WifiOff,
  BarChart3,
  MessageSquare
} from 'lucide-react';
import { apiClient } from '@/api/client';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const location = useLocation();

  // Check API connection on mount and periodically
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const connected = await apiClient.testConnection();
        setIsConnected(connected);
      } catch {
        setIsConnected(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const navigation = [
    { name: 'Home', href: '/', icon: Home },
    { name: 'Sessions', href: '/sessions', icon: FileText },
    { name: 'Graph', href: '/graph', icon: Network },
    { name: 'Entities', href: '/entities', icon: Database },
    { name: 'Insights', href: '/insights', icon: BarChart3 },
    { name: 'RAG', href: '/rag', icon: MessageSquare },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gradient">Code Atlas</h1>
          <button
            className="lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-6 h-6 text-gray-500" />
          </button>
        </div>

        <nav role="navigation" className="mt-6 px-3">
          <div className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`
                    group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors duration-200
                    ${isActive(item.href)
                      ? 'bg-atlas-blue-100 text-atlas-blue-700 border-r-2 border-atlas-blue-700'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                    }
                  `}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500">
            <p>Code Atlas v1.0.0</p>
            <p className="mt-1">Transform Claude sessions into knowledge</p>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <div className="sticky top-0 z-10 bg-white shadow-sm border-b border-gray-200">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
            <button
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-6 h-6 text-gray-500" />
            </button>

            <div className="flex items-center space-x-2">
              {isConnected === null ? (
                <>
                  <div className="text-sm text-gray-400">Checking API...</div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" />
                </>
              ) : isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-500" />
                  <div className="text-sm text-green-600">Connected</div>
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-500" />
                  <div className="text-sm text-red-600">Disconnected</div>
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                </>
              )}
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="py-6">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;