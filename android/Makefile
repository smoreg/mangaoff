.PHONY: apk clean install

APK_OUT = ../mangaoff.apk

apk:
	./gradlew assembleDebug
	cp app/build/outputs/apk/debug/app-debug.apk $(APK_OUT)
	@echo "APK готов: $(APK_OUT)"

clean:
	./gradlew clean

install: apk
	adb install $(APK_OUT)
