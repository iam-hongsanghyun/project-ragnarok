import React, { createContext, useContext } from 'react';
import type { DateFormat } from './useSettings';

const DateFormatContext = createContext<DateFormat>('auto');

export function DateFormatProvider({ value, children }: { value: DateFormat; children: React.ReactNode }) {
  return <DateFormatContext.Provider value={value}>{children}</DateFormatContext.Provider>;
}

export function useDateFormat(): DateFormat {
  return useContext(DateFormatContext);
}
