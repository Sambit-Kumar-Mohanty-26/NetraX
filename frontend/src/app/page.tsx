"use client";

import { useEffect, useState, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface Alert {
  id: string;
  source: string;
  timestamp: string;
  video_id: string;
  confidence: number;
  risk_score: number;
  region: string;
  response: string;
  level: string;
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [regionData, setRegionData] = useState<any[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(false);

  // 🔥 We use refs to track state silently inside the setInterval without causing bugs
  const soundEnabledRef = useRef(false);
  const lastAlertIdRef = useRef<string | null>(null);

  // 🔊 Enable sound on click
  useEffect(() => {
    const enableSound = () => {
      setSoundEnabled(true);
      soundEnabledRef.current = true; // Update the ref immediately for the interval
      window.removeEventListener("click", enableSound);
    };
    window.addEventListener("click", enableSound);
    
    return () => {
      window.removeEventListener("click", enableSound);
    };
  }, []);

  // 🔁 Fetch alerts (Fixed the useEffect Dependency Bug)
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch("http://localhost:5000/api/alerts");
        
        // Failsafe in case the backend returns a non-JSON error page
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        
        const data = await res.json();

        // Play sound if there is a NEW alert and sound is enabled
        const latestAlertId = data[0]?.id;
        if (lastAlertIdRef.current && latestAlertId !== lastAlertIdRef.current) {
          if (soundEnabledRef.current) {
            const audio = new Audio(
              "https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg"
            );
            audio.play().catch(() => {}); // Catch prevents errors if browser blocks autoplay
          }
        }
        
        // Update our silent tracker
        if (latestAlertId) {
          lastAlertIdRef.current = latestAlertId;
        }

        setAlerts(data);

        const counts: any = {};
        data.forEach((a: Alert) => {
          const region = a.region || "Global";
          counts[region] = (counts[region] || 0) + 1;
        });

        const chart = Object.keys(counts).map((key) => ({
          region: key,
          count: counts[key],
        }));

        setRegionData(chart);
      } catch (error) {
        // This will quietly log if your backend is offline instead of crashing the app
        console.error("Failed to fetch alerts. Is localhost:5000 running?", error);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 2000);
    
    return () => clearInterval(interval);
  }, []); // 🔥 EMPTY ARRAY: Interval starts once and never restarts!

  // Helper functions for dynamic styling
  const getRiskColor = (risk: number) => {
    if (risk > 80) return "bg-red-500";
    if (risk > 60) return "bg-orange-500";
    return "bg-yellow-500";
  };

  const getLevelColor = (level: string) => {
    if (level === "HIGH") return "text-red-600";
    if (level === "MEDIUM") return "text-orange-500";
    return "text-yellow-600";
  };

  // 🌍 Exact Map positions
  const positions: Record<string, { top: string; left: string }> = {
    India: { top: "55%", left: "65%" },
    US: { top: "45%", left: "25%" },
    UK: { top: "35%", left: "48%" },
    Brazil: { top: "65%", left: "35%" },
    Indonesia: { top: "60%", left: "75%" },
    Global: { top: "50%", left: "50%" },
  };

  const highRisk = alerts.filter((a) => a.risk_score > 80).length;
  const avgConfidence =
    alerts.length > 0
      ? Math.round(
          alerts.reduce((sum, a) => sum + a.confidence, 0) / alerts.length
        )
      : 0;

  return (
    <div className="min-h-screen bg-gray-50 p-8 text-gray-900">
      {/* SOUND NOTICE */}
      {!soundEnabled && (
        <div className="bg-yellow-300 text-black px-4 py-2 rounded mb-4 text-center cursor-pointer shadow-sm">
          🔊 Click anywhere to enable alert sound
        </div>
      )}

      {/* HEADER */}
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">
          Netra<span className="text-blue-500">X</span>
        </h1>
        <span className="text-red-500 font-semibold text-sm flex items-center gap-2">
          <span className="animate-pulse">●</span> LIVE
        </span>
      </div>

      {/* STATS */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <p className="text-gray-500 text-sm font-medium">Live Alerts Today</p>
          <h2 className="text-3xl font-bold mt-2">{alerts.length}</h2>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <p className="text-gray-500 text-sm font-medium">High-Risk Events</p>
          <h2 className="text-3xl font-bold mt-2">{highRisk}</h2>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <p className="text-gray-500 text-sm font-medium">Avg. Confidence</p>
          <h2 className="text-3xl font-bold mt-2">{avgConfidence}%</h2>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="grid grid-cols-3 gap-6">
        {/* ALERT FEED */}
        <div className="col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col">
          <h2 className="text-lg font-semibold mb-4 shrink-0">Real-Time Event Feed</h2>

          <div className="flex-1 min-h-0 overflow-y-auto pr-2 space-y-4">
            {alerts.length === 0 ? (
              <p className="text-gray-400 italic">Waiting for alerts...</p>
            ) : (
              alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="relative overflow-hidden bg-white border border-gray-100 p-5 rounded-lg hover:bg-gray-50 transition duration-300 shadow-sm hover:shadow-md hover:border-red-200 group"
                >
                  <div className="absolute inset-0 bg-red-500/5 blur-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>

                  <div className="relative z-10 w-full">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-bold text-gray-800">{alert.source}</span>
                      <span className="text-xs text-gray-500 font-medium">
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <p className="text-gray-700 text-sm mb-1">🎬 {alert.video_id}</p>

                    <p className="text-sm text-gray-500 mb-2">
                      🌍 {alert.region} | 📊 {alert.confidence}%
                    </p>

                    <p className="text-sm text-blue-600 font-medium">
                      ⚡ {alert.response}
                    </p>

                    <p className={`text-xs mt-1 font-bold ${getLevelColor(alert.level)}`}>
                      Level: {alert.level}
                    </p>

                    <div className="mt-3">
                      <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`${getRiskColor(alert.risk_score)} h-1.5 rounded-full transition-all duration-500`}
                          style={{ width: `${alert.risk_score}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="space-y-6">
          {/* MAP */}
          <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
            <h2 className="text-lg font-semibold mb-2">Global Activity</h2>

            <div className="relative w-full h-[150px] bg-blue-50/50 rounded overflow-hidden border border-gray-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="https://upload.wikimedia.org/wikipedia/commons/8/80/World_map_-_low_resolution.svg"
                alt="World Map"
                className="w-full h-full opacity-40 object-cover"
              />

              {regionData.map((r, i) => {
                const pos = positions[r.region] || positions["Global"];
                
                return (
                  <div
                    key={i}
                    className="absolute"
                    style={{ top: pos.top, left: pos.left }}
                  >
                    <div className="relative flex items-center justify-center">
                      <div className="w-3 h-3 bg-red-500 rounded-full animate-ping absolute"></div>
                      <div className="w-3 h-3 bg-red-500 rounded-full relative z-10"></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* REGION STATS */}
          <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
            <h2 className="text-lg font-semibold mb-3">
              Top Regions by Activity
            </h2>

            <div className="max-h-[200px] overflow-y-auto pr-2">
              {regionData.map((r) => (
                <div key={r.region} className="mb-3">
                  <div className="flex justify-between text-sm font-medium mb-1">
                    <span>{r.region}</span>
                    <span>{r.count}</span>
                  </div>

                  <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(r.count * 20, 100)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CHART */}
          <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
            <h2 className="text-lg font-semibold mb-3">Region Stats Chart</h2>

            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={regionData}>
                <XAxis dataKey="region" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip 
                  cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}