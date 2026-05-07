package com.alphamini.setup

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.navigation.compose.rememberNavController
import com.alphamini.setup.navigation.AppNavigation
import com.alphamini.setup.ui.theme.AlphaMiniSetupTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            AlphaMiniSetupTheme {
                val navController = rememberNavController()
                AppNavigation(navController = navController)
            }
        }
    }
}

