"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Wifi, WifiOff, RefreshCw, Activity } from "lucide-react";
import { getMeshHealth } from "@/lib/api";

export default function MeshPage() {
  const [health, setHealth]   = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try { setHealth(await getMeshHealth()); }
    catch(e) {}
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link href="/" className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700"><ArrowLeft size={18} /></Link>
        <div>
          <h1 className="text-xl font-bold">Mesh Monitor</h1>
          <p className="text-gray-400 text-sm">Live relay node status — refreshes every 5s</p>
        </div>
        <button onClick={refresh} className="ml-auto p-2 rounded-lg bg-gray-800">
          <RefreshCw size={18} className={loading ? "animate-spin text-emerald-400" : "text-gray-400"} />
        </button>
      </div>

      {health && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: "Total nodes",  value: health.relay_nodes.total,            color: "text-white" },
              { label: "With internet",value: health.relay_nodes.internet_capable, color: "text-emerald-400" },
              { label: "Offline only", value: health.relay_nodes.offline_only,     color: "text-yellow-400" },
            ].map(s => (
              <div key={s.label} className="bg-gray-800 rounded-xl p-4 border border-gray-700 text-center">
                <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-gray-400 text-xs mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={18} className="text-emerald-400" />
              <h2 className="font-semibold">Relay Nodes</h2>
            </div>
            <div className="space-y-3">
              {Object.entries(health.relay_nodes.nodes).map(([id, node]: [string, any]) => (
                <div key={id} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg">
                  <div>
                    <p className="text-sm font-mono text-gray-200">{id}</p>
                    <p className="text-xs text-gray-500">
                      Last seen: {new Date(node.last_seen * 1000).toLocaleTimeString()}
                    </p>
                  </div>
                  <span className={`flex items-center gap-1 text-xs px-3 py-1 rounded-full ${
                    node.had_internet ? "bg-emerald-900/50 text-emerald-400" : "bg-gray-700 text-gray-400"
                  }`}>
                    {node.had_internet ? <Wifi size={12} /> : <WifiOff size={12} />}
                    {node.had_internet ? "Internet" : "Mesh only"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h2 className="font-semibold mb-4">Transaction Stats</h2>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Total",        value: health.transactions.total,        color: "text-white" },
                { label: "Success",      value: health.transactions.success,      color: "text-emerald-400" },
                { label: "Failed",       value: health.transactions.failed,       color: "text-red-400" },
                { label: "Success rate", value: health.transactions.success_rate, color: "text-blue-400" },
              ].map(s => (
                <div key={s.label} className="text-center p-3 bg-gray-900 rounded-lg">
                  <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                  <p className="text-gray-400 text-xs">{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
