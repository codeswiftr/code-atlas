import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';
import { EntityResponse } from '@/types/api';

interface TopEntitiesCardProps {
  entities: EntityResponse[];
  isLoading?: boolean;
  error?: string | null;
}

const TopEntitiesCard: React.FC<TopEntitiesCardProps> = ({ entities, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
          <p className="text-gray-600 mt-2">Loading top entities...</p>
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

  const chartData = entities.slice(0, 10).map(entity => ({
    name: entity.name.length > 20 ? entity.name.substring(0, 20) + '...' : entity.name,
    fullName: entity.name,
    mentions: entity.mention_count || 0,
    type: entity.type,
  }));

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <TrendingUp className="w-5 h-5 text-atlas-blue-600 mr-2" />
          <h3 className="font-semibold">Top Entities</h3>
        </div>
        <span className="text-sm text-gray-600">{entities.length} entities</span>
      </div>

      {chartData.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No entities found</div>
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
                    `${value} mentions`,
                    props.payload.fullName
                  ]}
                />
                <Bar dataKey="mentions" fill="#38BDF8" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 max-h-48 overflow-y-auto">
            {entities.slice(0, 10).map((entity, index) => (
              <div
                key={entity.id}
                className="flex items-center justify-between p-2 border border-gray-200 rounded hover:bg-gray-50"
              >
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-500 w-6">#{index + 1}</span>
                  <div>
                    <div className="font-medium text-sm">{entity.name}</div>
                    <div className="text-xs text-gray-500">{entity.type}</div>
                  </div>
                </div>
                <div className="text-sm font-semibold text-atlas-blue-600">
                  {entity.mention_count || 0}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default TopEntitiesCard;

