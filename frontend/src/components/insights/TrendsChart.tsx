import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';

interface TrendData {
  date: string;
  counts: Record<string, number>;
  total: number;
}

interface TrendsChartProps {
  trends: TrendData[];
  isLoading?: boolean;
  error?: string | null;
}

const TrendsChart: React.FC<TrendsChartProps> = ({ trends, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
          <p className="text-gray-600 mt-2">Loading trends...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-red-800 font-medium">Error</div>
          <div className="text-red-600 text-sm mt-1">{error}</div>
        </div>
      </div>
    );
  }

  // Get all unique entity types
  const entityTypes = new Set<string>();
  trends.forEach(trend => {
    Object.keys(trend.counts).forEach(type => entityTypes.add(type));
  });

  const colors = ['#38BDF8', '#A78BFA', '#34D399', '#FB923C', '#F87171', '#10B981'];
  const colorMap: Record<string, string> = {};
  Array.from(entityTypes).forEach((type, index) => {
    colorMap[type] = colors[index % colors.length];
  });

  const chartData = trends.map(trend => {
    const data: Record<string, any> = {
      date: new Date(trend.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      total: trend.total,
    };
    Object.keys(trend.counts).forEach(type => {
      data[type] = trend.counts[type];
    });
    return data;
  });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <TrendingUp className="w-5 h-5 text-atlas-blue-600 mr-2" />
          <h3 className="font-semibold">Entity Creation Trends</h3>
        </div>
        <span className="text-sm text-gray-600">{trends.length} data points</span>
      </div>

      {chartData.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No trend data available</div>
      ) : (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="total" 
                stroke="#38BDF8" 
                strokeWidth={2}
                name="Total"
              />
              {Array.from(entityTypes).map(type => (
                <Line
                  key={type}
                  type="monotone"
                  dataKey={type}
                  stroke={colorMap[type]}
                  strokeWidth={1.5}
                  name={type}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default TrendsChart;

