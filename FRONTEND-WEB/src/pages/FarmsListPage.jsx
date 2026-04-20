import { Link } from 'react-router-dom';
import { Tractor, MapPin, Phone, Leaf, Droplets, AlertTriangle, ChevronRight } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { useFarms } from '../hooks/useFarms';

function getMoistureClass(m) {
  if (m < 35) return 'text-danger-600 bg-danger-50';
  if (m < 60) return 'text-amber-600 bg-amber-50';
  return 'text-teal-600 bg-teal-50';
}

export default function FarmsListPage() {
  const { data: farms, isLoading, error } = useFarms();

  return (
    <div className="space-y-6">
      <PageHeader 
        titleKey="page.farms.title" 
        descKey="page.farms.desc" 
        icon={Tractor} 
      />

      {error && (
        <div className="card border-danger-200 bg-danger-50 flex items-center gap-3 text-danger-500">
          <AlertTriangle size={18} />
          <p className="text-sm">{error.message}</p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card animate-pulse h-24 bg-neutral-100" />
          ))}
        </div>
      )}

      {!isLoading && (!farms || farms.length === 0) && (
        <div className="card flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
          <Tractor size={36} />
          <p className="text-sm">No farms registered yet.</p>
        </div>
      )}

      <div className="space-y-3">
        {(farms || []).map((farm) => (
          <Link
            key={farm.id}
            to={`/farms/${farm.id}`}
            className="card flex items-center gap-4 hover:border-primary-200 hover:bg-primary-50 transition-colors group"
            id={`farm-card-${farm.id}`}
          >
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Tractor size={18} className="text-primary-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-semibold text-neutral-800 group-hover:text-primary-700">{farm.name}</h2>
                <span className="text-xs bg-neutral-100 text-neutral-500 px-2 py-0.5 rounded-full">{farm.season}</span>
              </div>
              <div className="flex items-center gap-3 mt-1 flex-wrap text-xs text-neutral-400">
                <span className="flex items-center gap-1"><MapPin size={11} /> {farm.location}</span>
                <span className="flex items-center gap-1"><Leaf size={11} /> {farm.crop_type}</span>
                <span className="flex items-center gap-1"><Phone size={11} /> {farm.farmer_name}</span>
              </div>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${getMoistureClass(farm.soil_moisture_avg)}`}>
                <Droplets size={11} />
                {Math.round(farm.soil_moisture_avg)}%
              </div>
              <span className="text-xs text-neutral-400 hidden sm:block">{farm.area_ha} ha</span>
              <ChevronRight size={15} className="text-neutral-300 group-hover:text-primary-400 transition-colors" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
