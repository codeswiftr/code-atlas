import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, FileText, Network, Search, BarChart3, Loader2 } from 'lucide-react';
import { apiClient } from '@/api/client';

interface GraphStats {
  entity_count: number;
  relationship_count: number;
  entity_types: Record<string, number>;
}

interface ProcessingStats {
  total_sessions_processed: number;
  total_cost: number;
}

const HomePage: React.FC = () => {
  // Fetch graph stats
  const { data: graphStats, isLoading: graphLoading } = useQuery<GraphStats>({
    queryKey: ['graph-stats'],
    queryFn: () => apiClient.getGraphStats(),
    retry: 1,
    staleTime: 60000, // 1 minute
  });

  // Fetch processing stats
  const { data: processingStats, isLoading: processingLoading } = useQuery<ProcessingStats>({
    queryKey: ['processing-stats'],
    queryFn: () => apiClient.getProcessingStats(),
    retry: 1,
    staleTime: 60000,
  });

  const isLoading = graphLoading || processingLoading;

  const features = [
    {
      icon: FileText,
      title: 'Session Discovery',
      description: 'Automatically discover and parse Claude Code session files from your projects.',
      link: '/sessions',
    },
    {
      icon: Network,
      title: 'Knowledge Graph',
      description: 'Explore entities and relationships in an interactive graph visualization.',
      link: '/graph',
    },
    {
      icon: Search,
      title: 'Entity Search',
      description: 'Search across concepts, files, tools, and problems with fuzzy matching.',
      link: '/entities',
    },
    {
      icon: BarChart3,
      title: 'Processing Insights',
      description: 'Monitor processing progress and analyze extraction statistics.',
      link: '/sessions',
    },
  ];

  const formatNumber = (num: number | undefined): string => {
    if (num === undefined) return '0';
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num.toString();
  };

  const formatCost = (cost: number | undefined): string => {
    if (cost === undefined) return '$0.00';
    return `$${cost.toFixed(2)}`;
  };

  const stats = [
    {
      label: 'Sessions Processed',
      value: formatNumber(processingStats?.total_sessions_processed),
    },
    {
      label: 'Entities Extracted',
      value: formatNumber(graphStats?.entity_count),
    },
    {
      label: 'Relationships Found',
      value: formatNumber(graphStats?.relationship_count),
    },
    {
      label: 'Processing Cost',
      value: formatCost(processingStats?.total_cost),
    },
  ];

  return (
    <div className="space-y-8">
      {/* Hero section */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-gradient">
          Code Atlas
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Transform your Claude Code sessions into a searchable knowledge graph.
          Discover insights, track patterns, and navigate your development knowledge.
        </p>
        <div className="flex justify-center space-x-4">
          <Link to="/sessions" className="btn-primary">
            Get Started
            <ArrowRight className="ml-2 w-4 h-4" />
          </Link>
          <Link to="/graph" className="btn-outline">
            View Demo
          </Link>
        </div>
      </div>

      {/* Stats section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div key={index} className="card text-center">
            <div className="text-2xl font-bold text-atlas-blue-600">
              {isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
              ) : (
                stat.value
              )}
            </div>
            <div className="text-sm text-gray-600 mt-1">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Features grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {features.map((feature, index) => {
          const Icon = feature.icon;
          return (
            <Link
              key={index}
              to={feature.link}
              className="card hover:shadow-md transition-shadow duration-200 group"
            >
              <div className="flex items-start space-x-4">
                <div className="p-3 bg-atlas-blue-100 rounded-lg group-hover:bg-atlas-blue-200 transition-colors">
                  <Icon className="w-6 h-6 text-atlas-blue-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-gray-600">
                    {feature.description}
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Quick start guide */}
      <div className="card">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          Quick Start Guide
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="w-8 h-8 bg-atlas-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-3">
              1
            </div>
            <h3 className="font-semibold mb-2">Discover Sessions</h3>
            <p className="text-sm text-gray-600">
              Scan your Claude Code projects to find session files
            </p>
          </div>
          <div className="text-center">
            <div className="w-8 h-8 bg-atlas-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-3">
              2
            </div>
            <h3 className="font-semibold mb-2">Process & Extract</h3>
            <p className="text-sm text-gray-600">
              Extract entities and relationships using LLM or heuristics
            </p>
          </div>
          <div className="text-center">
            <div className="w-8 h-8 bg-atlas-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-3">
              3
            </div>
            <h3 className="font-semibold mb-2">Explore Knowledge</h3>
            <p className="text-sm text-gray-600">
              Navigate the knowledge graph and discover insights
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;