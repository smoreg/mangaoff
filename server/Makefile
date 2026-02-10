.PHONY: build run clean deploy

BINARY=mangaoff-server
SERVER=smoreg.dev

build:
	go build -o $(BINARY) .

run: build
	./$(BINARY) -data ./testdata

clean:
	rm -f $(BINARY)

# Build for Linux and deploy to server
deploy:
	GOOS=linux GOARCH=amd64 go build -o $(BINARY) .
	scp $(BINARY) $(SERVER):/opt/mangaoff/bin/
	ssh $(SERVER) 'sudo systemctl restart mangaoff'
	rm $(BINARY)

# Create testdata directory structure for local development
testdata:
	mkdir -p testdata/chainsaw-man/chapters
	mkdir -p testdata/chainsaw-man/covers
