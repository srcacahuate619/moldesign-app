"use client";

/**
 * Tiny Web Animations API adapter used by the UI.  Keeping animation as a
 * browser primitive avoids shipping a second animation runtime in the
 * desktop bundle; scientific state never depends on these effects.
 */
export type WebAnimationTarget = Element | Element[] | NodeListOf<Element>;

export type WebAnimationOptions = KeyframeAnimationOptions & {
  onComplete?: () => void;
};

function elements(target: WebAnimationTarget): Element[] {
  if (typeof Element !== "undefined" && target instanceof Element) return [target];
  return Array.from(target as Iterable<Element>);
}

export function animateElements(
  target: WebAnimationTarget,
  keyframes: Keyframe[] | PropertyIndexedKeyframes,
  options: WebAnimationOptions = {},
): Animation[] {
  const { onComplete, ...animationOptions } = options;
  const nodes = elements(target);
  const animations = nodes.map((node) => {
    const animation = (node as HTMLElement).animate(keyframes, animationOptions);
    if (onComplete) animation.finished.then(onComplete).catch(() => undefined);
    return animation;
  });
  return animations;
}

export function cancelAnimations(target: WebAnimationTarget): void {
  for (const node of elements(target)) node.getAnimations().forEach((animation) => animation.cancel());
}

