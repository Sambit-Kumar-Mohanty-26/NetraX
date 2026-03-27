"use client";

import { useEffect, useState } from "react";
import { collection, onSnapshot, query, orderBy } from "firebase/firestore";
import { db } from "../firebase";

interface Alert {
  id: string;
  source: string;
  timestamp: any;
  video_id: string;
  confidence: number;
  risk_score: number;
  region: string;
}

interface RegionCount {
  [key: string]: number;
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [regionCounts, setRegionCounts] = useState<RegionCount>({});

  useEffect(() => {
    const q = query(collection(db, "alerts"), orderBy("timestamp", "desc"));
    
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const liveAlerts: Alert[] = [];
      const counts: RegionCount = {};

      snapshot.forEach((doc) => {
        const data = doc.data() as Omit<Alert, 'id'>;
        liveAlerts.push({ id: doc.id, ...data });

        if (data.region) {
          counts[data.region] = (counts[data.region] || 0) + 1;
        }
      });
      
      setAlerts(liveAlerts);
      setRegionCounts(counts);
    });

    return () => unsubscribe();
  }, []);

  const getRiskColor = (risk: number) => {
    if (risk > 80) return "bg-red-500";
    if (risk > 60) return "bg-orange-500";
    return "bg-yellow-500";
  };
  
  const getHeatmapColor = (count: number) => {
    if (count > 5) return "bg-red-800";
    if (count > 2) return "bg-red-600";
    return "bg-red-400";
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-10 font-sans">
      <header className="mb-8">
        <h1 className="text-4xl font-bold text-blue-400">NetraX Live Monitoring</h1>
        <p className="text-gray-400">Real-time piracy detection and intelligence dashboard</p>
      </header>
      
      <main className="grid grid-cols-3 gap-8">
        <div className="col-span-2 bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-2xl font-semibold mb-4 text-red-400">🚨 Live Piracy Alerts</h2>
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
            {alerts.length === 0 ? (
              <p className="text-gray-400">Scanning streams... No piracy detected yet.</p>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="border-l-4 border-red-500 bg-gray-700 p-4 rounded-r-lg">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-lg">{alert.source}</span>
                    <span className="text-sm text-gray-400">
                      {alert.timestamp && typeof alert.timestamp.toDate === 'function' 
                        ? new Date(alert.timestamp.toDate()).toLocaleTimeString() 
                        : 'Processing...'}
                    </span>
                  </div>
                  <p className="text-gray-300 mt-1">Video ID: <span className="text-white font-mono">{alert.video_id}</span></p>
                  <div className="mt-3">
                    <label className="text-sm font-medium text-gray-400">Viral Risk</label>
                    <div className="w-full bg-gray-600 rounded-full h-4 mt-1">
                      <div className={`${getRiskColor(alert.risk_score)} h-4 rounded-full`} style={{ width: `${alert.risk_score}%` }}></div>
                    </div>
                    <p className="text-right text-sm font-bold">{alert.risk_score}%</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="col-span-1 bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-2xl font-semibold mb-4 text-orange-400">🔥 Piracy Heatmap</h2>
           <div className="space-y-3">
            {Object.entries(regionCounts).length > 0 ? (
              Object.entries(regionCounts)
                .sort(([, a], [, b]) => b - a)
                .map(([region, count]) => (
                  <div key={region} className="flex justify-between items-center">
                    <span className="font-medium text-lg">{region}</span>
                    <div className={`px-3 py-1 text-sm font-bold rounded-full ${getHeatmapColor(count)}`}>
                      {count} {count > 1 ? 'Alerts' : 'Alert'}
                    </div>
                  </div>
                ))
            ) : (
              <p className="text-gray-400">Awaiting geo-data...</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}