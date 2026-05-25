"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import styles from "./MaryLandingSplash.module.css";

const messages = [
  "Hi Mary!",
  "I’ve been working on this project for a while, and I’m excited to finally share it with you.",
  "The goal of this device is to give us another way to communicate while we’re apart.",
  "I wanted to replicate the feeling of surprising you with flowers or seeing each other on e-way.",
  "The picture frame you just unboxed contains a small computer and an e-ink display. I made one for myself too.",
  "The idea is we can send each other messages, pictures, links, etc. and our frames will update to show something new every day.",
  "I plan to send you all the cool photos I take this summer and leave you cute messages.",
  "So you can always know when I’m thinking about you <3",
  "However…",
  "I have since decided to add a bunch of other features to your frame.",
  "It now serves as a daily companion to show you weather, today’s events, news headlines, funny jokes, or anything else you need.",
  "You can set up a schedule through this website and leave it running for months without recharging.",
  "I built it to last forever, so no matter where you go or what you do it will be useful.",
  "Definitely check out the ‘You and Me’ module.",
  "Anyway, I hope you like it and I wish you the happiest of (belated) birthdays.",
  "Can’t wait to hold you in my arms again soon (even if confined to the car).",
  "Love, Tao",
];

type VantaEffect = {
  destroy: () => void;
  setOptions?: (options: Record<string, unknown>) => void;
};

type VantaBirdsFactory = (options: Record<string, unknown>) => VantaEffect;

const SPLASH_CHROME_COLOR = "#f7f4ee";

export default function MaryLandingSplash() {
  const vantaHostRef = useRef<HTMLDivElement | null>(null);
  const vantaEffectRef = useRef<VantaEffect | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fadeFrameRef = useRef<number | null>(null);
  const [messageIndex, setMessageIndex] = useState(0);
  const introComplete = messageIndex >= messages.length;
  const progress = Math.min(messageIndex + 1, messages.length);

  useEffect(() => {
    document.documentElement.classList.add("mary-splash-active");

    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    const previousThemeColor = themeColorMeta?.getAttribute("content") ?? null;
    themeColorMeta?.setAttribute("content", SPLASH_CHROME_COLOR);

    return () => {
      document.documentElement.classList.remove("mary-splash-active");
      if (themeColorMeta) {
        if (previousThemeColor) {
          themeColorMeta.setAttribute("content", previousThemeColor);
        } else {
          themeColorMeta.removeAttribute("content");
        }
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadBirds() {
      const [threeModule, birdsModule] = await Promise.all([
        import("three"),
        import("vanta/dist/vanta.birds.min.js"),
      ]);

      if (cancelled || !vantaHostRef.current) return;

      const createBirds = (birdsModule.default ?? birdsModule) as VantaBirdsFactory;
      vantaEffectRef.current = createBirds({
        el: vantaHostRef.current,
        THREE: threeModule,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        backgroundColor: 0xf7f4ee,
        backgroundAlpha: 1,
        color1: 0xff0000,
        color2: 0x247eb9,
        birdSize: 1,
        wingSpan: 30,
        speedLimit: 5,
        separation: 25,
        alignment: 20,
        cohesion: 20,
        quantity: 4,
        scale: 1,
        scaleMobile: 1,
      });
    }

    loadBirds();

    return () => {
      cancelled = true;
      vantaEffectRef.current?.destroy();
      vantaEffectRef.current = null;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (fadeFrameRef.current !== null) {
        window.cancelAnimationFrame(fadeFrameRef.current);
      }
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  function startBirdAudio() {
    if (audioRef.current) return;

    const audio = new Audio("/audio/spring-birds-loop.m4a");
    audio.loop = true;
    audio.preload = "auto";
    audio.volume = 0;
    audioRef.current = audio;

    audio.play().then(() => {
      const targetVolume = 0.3;
      const durationMs = 3000;
      const startTime = performance.now();

      function fade(now: number) {
        const progressRatio = Math.min((now - startTime) / durationMs, 1);
        audio.volume = targetVolume * progressRatio;
        if (progressRatio < 1) {
          fadeFrameRef.current = window.requestAnimationFrame(fade);
        } else {
          fadeFrameRef.current = null;
        }
      }

      fadeFrameRef.current = window.requestAnimationFrame(fade);
    }).catch(() => {
      audioRef.current = null;
    });
  }

  function advanceIntro() {
    if (!introComplete) {
      startBirdAudio();
      setMessageIndex((current) => current + 1);
    }
  }

  return (
    <section
      className={`${styles.shell} flex bg-paper px-5 py-8 text-ink sm:px-8 md:items-center md:px-10 md:py-14`}
    >
      <div ref={vantaHostRef} aria-hidden className={styles.vantaLayer} />
      <div aria-hidden className={styles.paperWash} />

      <div className="relative z-[3] mx-auto flex w-full max-w-5xl flex-1 items-center justify-center">
        {!introComplete ? (
          <button
            type="button"
            onClick={advanceIntro}
            className="group fixed inset-0 z-10 flex min-h-full w-full cursor-pointer flex-col items-center justify-center px-0 text-center outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-ink/40"
            aria-label="Show the next message"
          >
            <div className="pointer-events-none mx-4 flex min-h-[min(34rem,84dvh)] w-[calc(100%-2rem)] max-w-5xl flex-col items-center justify-center rounded-[2rem] border border-ink/10 bg-paper/45 px-5 py-10 shadow-2xl shadow-ink/10 backdrop-blur-[2px] transition group-hover:bg-paper/55 sm:mx-6 sm:px-10 md:px-16">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-ink-soft/75">
                A note for Mary
              </p>
              <p
                key={messageIndex}
                className={`${styles.message} mt-8 max-w-3xl font-display text-[clamp(2rem,9vw,4.5rem)] leading-tight text-ink md:leading-[1.08]`}
              >
                {messages[messageIndex]}
              </p>
              <div className="mt-10 flex flex-col items-center gap-4 text-sm text-ink-soft sm:mt-12">
                <span className={`${styles.pulse} rounded-full border border-ink/15 bg-white/70 px-4 py-2`}>
                  Tap or click anywhere to continue
                </span>
                <span className="font-medium tabular-nums">
                  {progress} / {messages.length}
                </span>
              </div>
            </div>
          </button>
        ) : (
          <div className={`${styles.message} w-full max-w-3xl rounded-[2rem] border border-ink/10 bg-paper/86 px-6 py-10 text-center shadow-2xl shadow-ink/10 backdrop-blur-sm sm:px-10 md:px-14 md:py-14`}>
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-ink-soft/75">
              Welcome Mary
            </p>
            <h1 className="mt-5 font-display text-4xl leading-tight text-ink sm:text-5xl md:text-6xl">
              Ready to set up your frame?
            </h1>
            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Link
                href="/sign-up"
                className="inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper shadow-lg shadow-ink/10 transition hover:bg-ink-soft"
              >
                Create an account
              </Link>
              <Link
                href="/sign-in"
                className="inline-flex items-center justify-center rounded-full border border-ink/20 bg-paper/80 px-6 py-3 text-sm font-semibold text-ink transition hover:bg-white"
              >
                Log in
              </Link>
            </div>
            <button
              type="button"
              onClick={() => setMessageIndex(0)}
              className="mt-7 text-sm font-medium text-ink-soft underline-offset-4 transition hover:text-ink hover:underline"
            >
              Replay the note
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
