import React from 'react';
import { createPortal } from 'react-dom';
import htm from 'https://esm.sh/htm@3.1.1?dev';

export const html = htm.bind(React.createElement);
export const { useState, useEffect, useMemo, useCallback, useRef } = React;
export const Fragment = React.Fragment;
export { React, createPortal };
