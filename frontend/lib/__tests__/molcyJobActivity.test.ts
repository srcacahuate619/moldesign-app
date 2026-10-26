import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "../activityNotifications";
import { watchMolcyJobActivity } from "../molcyJobActivity";
import type { MolcyJob } from "../molcy";

describe("application-wide Molcy completion", () => {
  let received: ActivityNotification[];
  let stop: (() => void) | undefined;
  const receive = (event: Event) => received.push((event as CustomEvent<ActivityNotification>).detail);
  beforeEach(() => { vi.useFakeTimers(); received=[]; window.localStorage.clear(); window.addEventListener(ACTIVITY_NOTIFICATION_EVENT,receive); });
  afterEach(() => { stop?.(); window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT,receive); vi.useRealTimers(); });
  const job = (estado: MolcyJob["estado"]) => ({id:"job-A",estado});
  it("tracks the job independently of the displayed workspace and emits one exact terminal", async () => {
    const list = vi.fn().mockResolvedValueOnce({trabajos:[job("renderizando")]}).mockResolvedValue({trabajos:[job("completo")]});
    stop=watchMolcyJobActivity("owner-A",{list});
    await vi.advanceTimersByTimeAsync(0);
    expect(received).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(3000);
    expect(received).toHaveLength(1);
    expect(received[0]).toMatchObject({source:"molcy",jobId:"job-A",ownerId:"owner-A",outcome:"completed",recovered:false});
    await vi.advanceTimersByTimeAsync(10000);
    expect(received).toHaveLength(1);
  });
  it("restores an interrupted pending job to Activity without replaying a native alert", async () => {
    window.localStorage.setItem("moldesign:molcy-terminal:v1:owner-A",JSON.stringify({"job-A":"renderizando"}));
    stop=watchMolcyJobActivity("owner-A",{list:vi.fn().mockResolvedValue({trabajos:[job("completo")]})});
    await vi.advanceTimersByTimeAsync(0);
    expect(received[0]).toMatchObject({recovered:true,silent:true,outcome:"completed"});
  });
  it("records voluntary cancellation as information with no progress or error outcome", async () => {
    const list=vi.fn().mockResolvedValueOnce({trabajos:[job("en_cola")]}).mockResolvedValue({trabajos:[job("cancelado")]});
    stop=watchMolcyJobActivity("owner-A",{list});
    await vi.advanceTimersByTimeAsync(3000);
    expect(received[0]).toMatchObject({status:"info",silent:true,outcome:"cancelled"});
    expect(received[0].progress).toBeNull();
  });
  it("discards responses after the owner subscription is disposed", async () => {
    let resolve!: (value: unknown) => void;
    const pending=new Promise(done => {resolve=done;});
    window.localStorage.setItem("moldesign:molcy-terminal:v1:owner-A",JSON.stringify({"job-A":"renderizando"}));
    stop=watchMolcyJobActivity("owner-A",{list:vi.fn().mockReturnValue(pending)});
    stop();
    resolve({trabajos:[job("completo")]});
    await vi.advanceTimersByTimeAsync(0);
    expect(received).toHaveLength(0);
  });
});
