import { useEffect, useState } from "react";
import type { ContractRow, Playbook, RedlineDeskData, Stamp, Summary, TestVector } from "./types";

async function get<T>(name: string): Promise<T> {
  const res = await fetch(`data/${name}.json`);
  if (!res.ok) throw new Error(`failed to load data/${name}.json`);
  return res.json() as Promise<T>;
}

async function tryGet<T>(name: string): Promise<T | null> {
  try {
    return await get<T>(name);
  } catch {
    return null;
  }
}

/** Loads the pipeline payloads (written by scripts/build_web.py). */
export function useRedlineDeskData() {
  const [data, setData] = useState<RedlineDeskData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [summary, contracts, playbook, vectors, stamp] = await Promise.all([
          get<Summary>("summary"),
          get<ContractRow[]>("contracts"),
          get<Playbook>("playbook"),
          get<{ vectors: TestVector[] }>("test-vectors"),
          tryGet<Stamp>("stamp"),
        ]);
        setData({ summary, contracts, playbook, vectors, stamp });
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  return { data, error };
}
