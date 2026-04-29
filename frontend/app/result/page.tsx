"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import Link from "next/link";
import { CheckCircle, XCircle, Home, RotateCcw } from "lucide-react";

function ResultContent() {
  const params    = useSearchParams();
  const status    = params.get("status");
  const packetId  = params.get("packet_id");
  const amount    = params.get("amount");
  const recipient = params.get("recipient");
  const sender    = params.get("sender") || "alice@upi";
  const txId      = params.get("tx_id") || "";
  const success   = status === "SUCCESS";

  useEffect(() => {
    // Save to sessionStorage so history page can read it
    if (!packetId) return;
    const tx = {
      packet_id:     packetId,
      tx_id:         txId,
      status:        status,
      sender_upi:    sender,
      recipient_upi: recipient,
      amount_paise:  parseInt(amount || "0"),
      time:          new Date().toLocaleTimeString(),
    };
    const existing = JSON.parse(sessionStorage.getItem("mesh_upi_txs") || "[]");
    // Avoid duplicates on re-render
    if (!existing.find((t: any) => t.packet_id === packetId)) {
      sessionStorage.setItem("mesh_upi_txs", JSON.stringify([tx, ...existing]));
    }
  }, [packetId]);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6 max-w-2xl mx-auto flex flex-col items-center justify-center">
      <div className={`w-24 h-24 rounded-full flex items-center justify-center mb-6 ${
        success ? "bg-emerald-900/50" : "bg-red-900/50"
      }`}>
        {success
          ? <CheckCircle size={48} className="text-emerald-400" />
          : <XCircle    size={48} className="text-red-400" />
        }
      </div>

      <h1 className="text-2xl font-bold mb-2">
        {success ? "Payment Sent!" : "Payment Failed"}
      </h1>

      {success && amount && (
        <p className="text-4xl font-bold text-emerald-400 mb-2">
          ₹{(parseInt(amount) / 100).toFixed(2)}
        </p>
      )}
      {recipient && <p className="text-gray-400 mb-6">to {recipient}</p>}

      <div className="w-full bg-gray-800 rounded-xl p-4 border border-gray-700 mb-8 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Status</span>
          <span className={success ? "text-emerald-400" : "text-red-400"}>{status}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Packet ID</span>
          <span className="text-gray-300 font-mono text-xs">{packetId?.slice(0, 20)}...</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">TX ID</span>
          <span className="text-gray-300 font-mono text-xs">{txId?.slice(0, 20)}...</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Encryption</span>
          <span className="text-gray-300 text-xs">AES-256-GCM + Ed25519</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Relay method</span>
          <span className="text-gray-300 text-xs">BLE mesh (simulated via WebRTC)</span>
        </div>
      </div>

      <div className="flex gap-4 w-full">
        <Link href="/" className="flex-1 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl flex items-center justify-center gap-2 border border-gray-700">
          <Home size={18} /> Home
        </Link>
        <Link href="/send" className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl flex items-center justify-center gap-2">
          <RotateCcw size={18} /> Send Again
        </Link>
      </div>
    </main>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-950" />}>
      <ResultContent />
    </Suspense>
  );
}
