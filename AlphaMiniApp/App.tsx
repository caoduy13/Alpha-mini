/**
 * Alpha Mini — React Native client (Android).
 */
import React from 'react';
import { StatusBar } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppProvider, useApp } from './src/context/AppContext';
import { useRobotStatus } from './src/hooks/useRobotStatus';
import { RootNavigator } from './src/navigation/RootNavigator';
import { navigationDarkTheme } from './src/theme/navigationTheme';
import { colors } from './src/theme';

function StatusBridge({ children }: { children: React.ReactNode }) {
  const { dispatch } = useApp();
  useRobotStatus(dispatch);
  return <>{children}</>;
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppProvider>
          <StatusBridge>
            <NavigationContainer theme={navigationDarkTheme}>
              <StatusBar
                barStyle="light-content"
                backgroundColor={colors.bg}
              />
              <RootNavigator />
            </NavigationContainer>
          </StatusBridge>
        </AppProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
