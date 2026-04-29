"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBalances, getMeshHealth } from "@/lib/api";
import { Wifi, WifiOff, Send, History, Activity, RefreshCw, Shield } from "lucide-react";

export default function Home() {
  const [balances, setBalances] = useState<any>(null);
  const [health, setHealth]     = useState<any>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string>("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [b, h] = await Promise.all([getBalances(), getMeshHealth()]);
      setBalances(b);
      setHealth(h);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (e: any) {
      setError("Cannot reach backend — is uvicorn running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">Mesh UPI</h1>
          <p className="text-gray-400 text-sm">Offline-first payments via BLE mesh</p>
        </div>
        <button onClick={refresh} className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700">
          <RefreshCw size={18} className={loading ? "animate-spin text-emerald-400" : "text-gray-400"} />
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-900/40 border border-red-700 rounded-xl text-red-300 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        {balances ? Object.entries(balances).map(([upi, data]: [string, any]) => (
          <div key={upi} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <p className="text-gray-400 text-xs mb-1">{upi}</p>
            <p className="text-2xl font-bold text-white">₹{data.rupees.toFixed(2)}</p>
            <p className="text-gray-500 text-xs">{data.paise} paise</p>
          </div>
        )) : (
          <>
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700 animate-pulse h-24" />
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700 animate-pulse h-24" />
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Link href="/send" className="bg-emerald-600 hover:bg-emerald-500 rounded-xl p-5 flex flex-col items-center gap-2 transition-colors">
          <Send size={24} />
          <span className="font-semibold">Send Money</span>
          <span className="text-emerald-200 text-xs text-center">Broadcast via BLE mesh</span>
        </Link>
        <Link href="/history" className="bg-gray-800 hover:bg-gray-700 rounded-xl p-5 flex flex-col items-center gap-2 transition-colors border border-gray-700">
          <History size={24} />
          <span className="font-semibold">History</span>
          <span className="text-gray-400 text-xs text-center">Past transactions</span>
        </Link>
      </div>

      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={18} className="text-emerald-400" />
          <h2 className="font-semibold">Mesh Network</h2>
          <Link href="/mesh" className="ml-auto text-xs text-emerald-400 hover:underline">Full monitor →</Link>
        </div>
        {health ? (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Relay nodes",   value: health.relay_nodes.total,          color: "text-emerald-400" },
              { label: "Transactions",  value: health.transactions.total,          color: "text-blue-400" },
              { label: "Success rate",  value: health.transactions.success_rate,   color: "text-yellow-400" },
            ].map(s => (
              <div key={s.label} className="text-center">
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-gray-400 text-xs">{s.label}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-16 animate-pulse bg-gray-700 rounded-lg" />
        )}
      </div>

      {health && (
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={18} className="text-blue-400" />
            <h2 className="font-semibold">Relay Nodes</h2>
          </div>
          <div className="space-y-2">
            {Object.entries(health.relay_nodes.nodes).map(([id, node]: [string, any]) => (
              <div key={id} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
                <span className="text-sm text-gray-300">{id}</span>
                <span className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                  node.had_internet ? "bg-emerald-900/50 text-emerald-400" : "bg-gray-700 text-gray-400"
                }`}>
                  {node.had_internet ? <Wifi size={12} /> : <WifiOff size={12} />}
                  {node.had_internet ? "Internet" : "Offline"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {lastRefresh && (
        <p className="text-center text-gray-600 text-xs">Last updated: {lastRefresh}</p>
      )}
    </main>
  );
}
