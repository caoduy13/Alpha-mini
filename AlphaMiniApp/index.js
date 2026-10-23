/**
 * @format
 */

import 'react-native-gesture-handler';
import { Buffer } from 'buffer';

(globalThis).Buffer = Buffer;

import {AppRegistry} from 'react-native';
import App from './App';
import {name as appName} from './app.json';

AppRegistry.registerComponent(appName, () => App);
