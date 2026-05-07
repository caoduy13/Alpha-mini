package com.alphamini.setup.navigation

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.alphamini.setup.ui.screens.PasswordScreen
import com.alphamini.setup.ui.screens.SuccessScreen
import com.alphamini.setup.ui.screens.WifiScanScreen
import com.alphamini.setup.viewmodel.UiState
import com.alphamini.setup.viewmodel.WifiSetupViewModel

@Composable
fun AppNavigation(navController: NavHostController) {
    val vm: WifiSetupViewModel = viewModel()

    NavHost(
        navController = navController,
        startDestination = Screen.WifiScan.route
    ) {
        composable(Screen.WifiScan.route) {
            WifiScanScreen(
                viewModel = vm,
                onWifiSelected = {
                    navController.navigate(Screen.Password.route)
                }
            )
        }
        composable(Screen.Password.route) {
            PasswordScreen(
                viewModel = vm,
                onBack = { navController.popBackStack() },
                onSuccess = {
                    if (vm.uiState.value == UiState.SUCCESS) {
                        navController.navigate(Screen.Success.route) {
                            popUpTo(Screen.WifiScan.route) { inclusive = false }
                        }
                    }
                }
            )
        }
        composable(Screen.Success.route) {
            SuccessScreen(
                viewModel = vm,
                onFinish = {
                    navController.popBackStack(Screen.WifiScan.route, inclusive = false)
                }
            )
        }
    }
}

