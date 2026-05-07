plugins {
    id("com.android.application") version "8.7.0" apply false
    // Dùng Kotlin 1.9.25 khớp với Compose Compiler 1.5.15
    id("org.jetbrains.kotlin.android") version "1.9.25" apply false
}

tasks.register<Delete>("clean") {
    delete(rootProject.buildDir)
}

