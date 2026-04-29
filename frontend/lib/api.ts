import axios from "axios";

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 30000,
});

export async function getBalances() {
  const r = await API.get("/api/v1/balances");
  return r.data;
}

export async function getMeshHealth() {
  const r = await API.get("/api/v1/mesh/health");
  return r.data;
}

export async function sendTransaction(packet: object) {
  const r = await API.post("/api/v1/transaction", packet);
  return r.data;
}

export async function getTransaction(packetId: string) {
  const r = await API.get(`/api/v1/transaction/${packetId}`);
  return r.data;
}

export async function getBankPubkey(ifscPrefix: string) {
  const r = await API.get(`/api/v1/bank/${ifscPrefix}/pubkey`);
  return r.data;
}

export default API;
