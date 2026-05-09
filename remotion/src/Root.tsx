import React from 'react';
import { Composition } from 'remotion';
import { ViciClip } from './ViciClip';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ViciClip"
        component={ViciClip}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          src: 'current_clip.mp4',
          hookText: 'Hook text here',
        }}
      />
    </>
  );
};
