import React from 'react';
import {
  AbsoluteFill,
  Audio,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  Sequence,
} from 'remotion';

type Props = {
  hookText: string;
  keyPoints: string[];
  voiceover: string;
  compound: string;
};

const CREAM = '#F5F3EF';
const NEAR_BLACK = '#1A1A1A';
const TEAL = '#00D4AA';

const FadeIn: React.FC<{
  from: number;
  children: React.ReactNode;
  duration?: number;
}> = ({ from, children, duration = 20 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const translateY = interpolate(frame, [from, from + duration], [16, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  return (
    <div style={{ opacity, transform: `translateY(${translateY}px)` }}>
      {children}
    </div>
  );
};

export const ViciTopicVideo: React.FC<Props> = ({
  hookText,
  keyPoints = [],
  voiceover,
  compound,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  // Global fade out last 15 frames
  const globalOpacity = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  // How long each key point shows (distribute evenly after hook)
  const hookDuration = fps * 3;
  const remainingFrames = durationInFrames - hookDuration - 60;
  const pointDuration = keyPoints.length > 0
    ? Math.floor(remainingFrames / keyPoints.length)
    : fps * 5;

  return (
    <AbsoluteFill style={{ backgroundColor: CREAM, opacity: globalOpacity }}>
      {/* Audio */}
      {voiceover && (
        <Audio src={staticFile(voiceover)} />
      )}

      {/* Top accent line */}
      <FadeIn from={5}>
        <div style={{
          position: 'absolute',
          top: 80,
          left: 60,
          right: 60,
          height: 2,
          backgroundColor: TEAL,
        }} />
      </FadeIn>

      {/* VICI wordmark */}
      <FadeIn from={0} duration={25}>
        <div style={{
          position: 'absolute',
          top: 50,
          left: 60,
          fontFamily: 'Georgia, serif',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '0.2em',
          color: NEAR_BLACK,
        }}>
          VICI
        </div>
      </FadeIn>

      {/* Hook -- shows first 3 seconds */}
      <Sequence from={0} durationInFrames={hookDuration + fps}>
        <AbsoluteFill style={{
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: '0 60px',
        }}>
          <FadeIn from={8} duration={30}>
            <div style={{
              fontFamily: 'Georgia, serif',
              fontSize: 64,
              fontWeight: 700,
              fontStyle: 'italic',
              color: NEAR_BLACK,
              lineHeight: 1.15,
              maxWidth: 920,
            }}>
              {hookText}
            </div>
          </FadeIn>
        </AbsoluteFill>
      </Sequence>

      {/* Key points -- each fades in sequentially */}
      {keyPoints.map((point, i) => {
        const startFrame = hookDuration + i * pointDuration;
        return (
          <Sequence
            key={i}
            from={startFrame}
            durationInFrames={pointDuration + 15}
          >
            <AbsoluteFill style={{
              justifyContent: 'center',
              alignItems: 'flex-start',
              padding: '0 60px',
            }}>
              <FadeIn from={0} duration={20}>
                <div style={{
                  fontFamily: 'Georgia, serif',
                  fontSize: 44,
                  fontWeight: 400,
                  color: NEAR_BLACK,
                  lineHeight: 1.4,
                  maxWidth: 880,
                  borderLeft: `4px solid ${TEAL}`,
                  paddingLeft: 32,
                }}>
                  {point.replace(/\*\*/g, '').replace(/--/g, '-')}
                </div>
              </FadeIn>
            </AbsoluteFill>
          </Sequence>
        );
      })}

      {/* Compound badge */}
      {compound && (
        <FadeIn from={20}>
          <div style={{
            position: 'absolute',
            top: 120,
            right: 60,
            backgroundColor: NEAR_BLACK,
            color: TEAL,
            padding: '6px 16px',
            fontFamily: 'sans-serif',
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: '0.12em',
          }}>
            {compound.toUpperCase()}
          </div>
        </FadeIn>
      )}

      {/* Bottom CTA */}
      <FadeIn from={hookDuration + fps}>
        <div style={{
          position: 'absolute',
          bottom: 60,
          left: 60,
          right: 60,
          fontFamily: 'Georgia, serif',
          fontSize: 20,
          fontStyle: 'italic',
          color: NEAR_BLACK,
          opacity: 0.65,
          textAlign: 'center',
        }}>
          Free research guide, link in bio. For research use only.
        </div>
      </FadeIn>

      {/* Bottom accent line */}
      <div style={{
        position: 'absolute',
        bottom: 100,
        left: 60,
        right: 60,
        height: 1,
        backgroundColor: NEAR_BLACK,
        opacity: 0.15,
      }} />
    </AbsoluteFill>
  );
};
