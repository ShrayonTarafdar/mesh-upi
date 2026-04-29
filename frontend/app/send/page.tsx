"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Send, Loader2, Shield } from "lucide-react";
import Link from "next/link";

export default function SendPage() {
  const router    = useRouter();
  const [sender,    setSender]    = useState("alice@upi");
  const [recipient, setRecipient] = useState("bob@upi");
  const [amount,    setAmount]    = useState("");
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  function handleSenderChange(val: string) {
    setSender(val);
    // Auto-switch recipient to avoid self-send
    if (val === recipient) {
      setRecipient(val === "alice@upi" ? "bob@upi" : "alice@upi");
    }
  }

  async function handleSend() {
    setError(null);
    const paise = Math.round(parseFloat(amount) * 100);
    if (!amount || paise <= 0)  { setError("Enter a valid amount"); return; }
    if (!recipient)              { setError("Enter recipient UPI ID"); return; }
    if (sender === recipient)    { setError("Cannot send money to yourself"); return; }
    if (paise < 100)             { setError("Minimum amount is ₹1 (100 paise)"); return; }

    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/demo/send`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender_upi:    sender,
          recipient_upi: recipient,
          amount_paise:  paise,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Transaction failed");
      const params = new URLSearchParams({
        packet_id: result.packet_id,
        tx_id:     result.tx_id  || "",
        status:    result.status,
        amount:    String(paise),
        recipient,
        sender,
      });
      router.push(`/result?${params.toString()}`);
    } catch (e: any) {
      setError(e.message || "Transaction failed");
    } finally {
      setLoading(false);
    }
  }

  const recipientOptions = ["alice@upi", "bob@upi"].filter(u => u !== sender);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link href="/" className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Send Money</h1>
          <p className="text-gray-400 text-sm">Broadcast via BLE mesh network</p>
        </div>
      </div>

      <div className="mb-6 p-4 bg-blue-900/30 border border-blue-700/50 rounded-xl flex gap-3">
        <Shield size={18} className="text-blue-400 mt-0.5 shrink-0" />
        <div className="text-sm text-blue-300">
          <p className="font-semibold mb-1">End-to-end encrypted</p>
          <p className="text-blue-400 text-xs">
            AES-256-GCM payload · RSA-OAEP session key · Ed25519 signed · 60s TTL
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">From</label>
          <select
            value={sender}
            onChange={e => handleSenderChange(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="alice@upi">alice@upi</option>
            <option value="bob@upi">bob@upi</option>
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">To (UPI ID)</label>
          <select
            value={recipient}
            onChange={e => setRecipient(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500"
          >
            {recipientOptions.map(u => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">Amount (₹)</label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-lg">₹</span>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="0.00"
              min="1"
              step="0.01"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl pl-8 pr-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 text-xl font-semibold"
            />
          </div>
          {amount && parseFloat(amount) > 0 && (
            <p className="text-gray-500 text-xs mt-1">
              = {Math.round(parseFloat(amount) * 100)} paise
            </p>
          )}
        </div>

        {error && (
          <div className="p-4 bg-red-900/40 border border-red-700 rounded-xl text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          {[50, 100, 200, 500].map(amt => (
            <button
              key={amt}
              onClick={() => setAmount(String(amt))}
              className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 border border-gray-700"
            >
              ₹{amt}
            </button>
          ))}
        </div>

        <button
          onClick={handleSend}
          disabled={loading || !amount || !recipient || sender === recipient}
          className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors"
        >
          {loading
            ? <><Loader2 size={20} className="animate-spin" /> Broadcasting packet...</>
            : <><Send size={20} /> Send via Mesh</>
          }
        </button>

        <p className="text-center text-gray-600 text-xs">
          Packet broadcast to nearby relay nodes via BLE.
          Any node with internet forwards to the bank.
        </p>
      </div>
    </main>
  );
}
