"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle, XCircle } from "lucide-react";

export default function HistoryPage() {
  const [txs, setTxs] = useState<any[]>([]);

  useEffect(() => {
    // Pull from Supabase directly via API
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/mesh/health`)
      .then(r => r.json())
      .then(h => {
        // For now show stats — full tx list comes from Supabase in the next step
      });

    // Load any transactions stored in sessionStorage (from this session)
    const stored = sessionStorage.getItem("mesh_upi_txs");
    if (stored) setTxs(JSON.parse(stored));
  }, []);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link href="/" className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700"><ArrowLeft size={18} /></Link>
        <div>
          <h1 className="text-xl font-bold">History</h1>
          <p className="text-gray-400 text-sm">Transactions this session</p>
        </div>
      </div>

      {txs.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg mb-2">No transactions yet</p>
          <Link href="/send" className="text-emerald-400 hover:underline text-sm">Send your first payment →</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {txs.map((tx, i) => (
            <div key={i} className="bg-gray-800 rounded-xl p-4 border border-gray-700 flex items-center gap-4">
              {tx.status === "SUCCESS"
                ? <CheckCircle size={20} className="text-emerald-400 shrink-0" />
                : <XCircle    size={20} className="text-red-400 shrink-0" />
              }
              <div className="flex-1">
                <p className="text-sm font-semibold">{tx.sender_upi} → {tx.recipient_upi}</p>
                <p className="text-xs text-gray-400 font-mono">{tx.packet_id?.slice(0,20)}...</p>
              </div>
              <div className="text-right">
                <p className="font-bold">₹{(tx.amount_paise/100).toFixed(2)}</p>
                <p className={`text-xs ${tx.status === "SUCCESS" ? "text-emerald-400" : "text-red-400"}`}>
                  {tx.status}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
