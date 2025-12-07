import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Wrench } from 'lucide-react';
import { EntityResponse } from '@/types/api';

interface PopularTool {
  entity: EntityResponse;
  usage_count: number;
}

interface PopularToolsCardProps {
  tools: PopularTool[];
  isLoading?: boolean;
  error?: string | null;
}

const PopularToolsCard: React.FC<PopularToolsCardProps> = ({ tools, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
          <p className="text-gray-600 mt-2">Loading popular tools...</p>
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

  const chartData = tools.slice(0, 10).map(tool => ({
    name: tool.entity.name.length > 15 ? tool.entity.name.substring(0, 15) + '...' : tool.entity.name,
    fullName: tool.entity.name,
    usage: tool.usage_count,
  }));

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <Wrench className="w-5 h-5 text-orange-600 mr-2" />
          <h3 className="font-semibold">Popular Tools</h3>
        </div>
        <span className="text-sm text-gray-600">{tools.length} tools</span>
      </div>

      {chartData.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No tools found</div>
      ) : (
        <>
          <div className="h-64 mb-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="name" 
                  angle={-45} 
                  textAnchor="end" 
                  height={80}
                  fontSize={12}
                />
                <YAxis />
                <Tooltip 
                  formatter={(value: number, _name: string, props: any) => [
                    `${value} uses`,
                    props.payload.fullName
                  ]}
                />
                <Bar dataKey="usage" fill="#FB923C" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 max-h-48 overflow-y-auto">
            {tools.slice(0, 10).map((tool, index) => (
              <div
                key={tool.entity.id}
                className="flex items-center justify-between p-2 border border-gray-200 rounded hover:bg-gray-50"
              >
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-500 w-6">#{index + 1}</span>
                  <div className="font-medium text-sm">{tool.entity.name}</div>
                </div>
                <div className="text-sm font-semibold text-orange-600">
                  {tool.usage_count} uses
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default PopularToolsCard;

