"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useLanguage } from "@/context/LanguageContext";
import { emitActivityNotification } from "@/lib/activityNotifications";
import { openNativeJobDestination, startNativeJobNotifications } from "@/lib/nativeJobNotifications";
import { watchMolcyJobActivity } from "@/lib/molcyJobActivity";

/** One application-wide listener; changing language or owner never replays old jobs. */
export function NativeJobNotifications() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const router = useRouter();
  const current = useRef({ owner: user?.user_id ?? null, t, router });
  current.current = { owner: user?.user_id ?? null, t, router };
  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    const getOwnerId = () => current.current.owner;
    void startNativeJobNotifications({
      getOwnerId,
      translate: key => current.current.t(key),
      openDestination: destination => openNativeJobDestination(destination, { getOwnerId, navigate: path => current.current.router.push(path) }),
      onOpenFailure: destination => {
        if (disposed || getOwnerId() !== destination.ownerId) return;
        emitActivityNotification({ id: `job-open:${destination.source}:${destination.taskId ?? destination.jobId}`, source: "general", status: "info", progress: null, titleKey: "nt_native_open_missing", silent: true, href: destination.source === "molcy" ? "/molcy" : destination.source === "batch" ? "/evaluation/batch" : "/evaluation" });
      },
    }).then(cleanup => { if (disposed) cleanup(); else stop = cleanup; }).catch(() => { /* Activity remains available if the native host is absent. */ });
    return () => { disposed = true; stop?.(); };
  }, []);
  const ownerId = user?.user_id;
  useEffect(() => ownerId ? watchMolcyJobActivity(ownerId) : undefined, [ownerId]);
  return null;
}
