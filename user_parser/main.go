package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"
	"regexp"

	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"
)

type NewsMessage struct {
	Text string   `json:"text"`
	Tags []string `json:"tags"`
}

type User struct {
	TelegramID          int64
	FirstName           string
	Username            sql.NullString
	IsPremium           bool
	IsAdmin             bool
	LLMModel            string
	AlertConfigGeneral  []string // Изменено с []byte на []string
	AlertConfigSpecific []string // Изменено с []byte на []string
	Language            string
}

type AlertMessage struct {
	UserID int64  `json:"user_id"`
	Text   string `json:"text"`
}

var (
	rdb *redis.Client
	db  *sql.DB
	ctx = context.Background()
)

func main() {
	// Инициализация Redis
	initRedis()

	// Инициализация MariaDB с повторными попытками
	initDBWithRetry(5, 5*time.Second)
	defer db.Close()

	// Запускаем обработчик новостей
	processNewsStream()
}

func initRedis() {
	redisPassword := os.Getenv("REDIS_PASSWORD")
	rdb = redis.NewClient(&redis.Options{
		Addr:     "redis:6379",
		Password: redisPassword,
		DB:       0,
	})

	// Проверяем подключение
	_, err := rdb.Ping(ctx).Result()
	if err != nil {
		log.Fatal("Failed to connect to Redis:", err)
	}
	log.Println("Connected to Redis")
}

func initDBWithRetry(maxAttempts int, delay time.Duration) {
	var err error
	for i := 0; i < maxAttempts; i++ {
		err = initDB()
		if err == nil {
			return
		}
		log.Printf("Attempt %d/%d failed: %v", i+1, maxAttempts, err)
		time.Sleep(delay)
	}
	log.Fatal("Failed to connect to database after multiple attempts:", err)
}

func initDB() error {
	dbUser := os.Getenv("DB_USER")
	dbPassword := os.Getenv("DB_PASSWORD")
	dbName := os.Getenv("DB_NAME")
	dbHost := os.Getenv("DB_HOST")
	dbPort := os.Getenv("DB_PORT")

	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s", dbUser, dbPassword, dbHost, dbPort, dbName)
	var err error
	db, err = sql.Open("mysql", dsn)
	if err != nil {
		return fmt.Errorf("failed to open database: %v", err)
	}

	// Устанавливаем максимальное количество открытых соединений
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(25)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Проверяем подключение
	err = db.Ping()
	if err != nil {
		return fmt.Errorf("failed to ping database: %v", err)
	}
	log.Println("Connected to database")
	return nil
}

func processNewsStream() {
	for {
		// Читаем сообщения из стрима news
		messages, err := rdb.XRead(ctx, &redis.XReadArgs{
			Streams: []string{"news", "0"},
			Count:   1,
			Block:   0,
		}).Result()

		if err != nil {
			log.Printf("Error reading from stream: %v", err)
			time.Sleep(1 * time.Second) // Задержка при ошибках чтения
			continue
		}

		for _, message := range messages {
			for _, xMessage := range message.Messages {
				processNewsMessage(xMessage.Values)
				// В будущем стоит перейти на Consumer Groups вместо удаления
				// rdb.XAck(ctx, "news", "news-consumers", xMessage.ID)
				rdb.XDel(ctx, "news", xMessage.ID)
			}
		}
	}
}

func processNewsMessage(values map[string]interface{}) {
    // Извлекаем текст и теги из значений Redis
    text, ok := values["text"].(string)
    if !ok {
        log.Printf("text is not a string")
        return
    }

    tagsStr, ok := values["tags"].(string)
    if !ok {
        log.Printf("tags is not a string")
        return
    }

    // Очищаем теги от водяных знаков и артефактов
    cleanedTagsStr := cleanRedisString(tagsStr)

    // Парсим строку тегов в массив строк
    var tags []string
    err := json.Unmarshal([]byte(cleanedTagsStr), &tags)
    if err != nil {
        log.Printf("Error unmarshaling tags: %v, original: %s, cleaned: %s", err, tagsStr, cleanedTagsStr)

        // Пытаемся извлечь теги из строки вручную
        tags = extractTagsFromString(cleanedTagsStr)
        if len(tags) == 0 {
            return
        }
    }

    // Создаем объект новости
    news := NewsMessage{
        Text: cleanRedisString(text),
        Tags: tags,
    }

    log.Printf("Processing news with %d tags: %v", len(news.Tags), news.Tags)

    // Получаем пользователей из БД с пагинацией по курсору
    processUsersWithCursorPagination(news)
}

func cleanRedisString(s string) string {
    // Удаляем водяные знаки и артефакты нейросети
    cleaned := strings.Map(func(r rune) rune {
        // Удаляем непечатаемые символы и специальные символы
        if r < 32 || r == 127 || r == '�' {
            return -1
        }

        // Удаляем специфические артефакты нейросети
        artifacts := []rune{'†', '⇥', '⇤', '‹', '›', '«', '»', '【', '】', '✨', '🚀', '📈', '📊', '💱', '💎'}
        for _, a := range artifacts {
            if r == a {
                return -1
            }
        }

        return r
    }, s)

    // Удаляем лишние пробелы
    cleaned = strings.TrimSpace(cleaned)

    return cleaned
}

func extractTagsFromString(s string) []string {
    // Пытаемся извлечь теги из строки различными способами

    // 1. Пытаемся найти JSON-массив
    if strings.HasPrefix(s, "[") && strings.HasSuffix(s, "]") {
        var tags []string
        if err := json.Unmarshal([]byte(s), &tags); err == nil {
            return tags
        }
    }

    // 2. Пытаемся найти теги в кавычках
    re := regexp.MustCompile(`["']([^"']+)["']`)
    matches := re.FindAllStringSubmatch(s, -1)
    if len(matches) > 0 {
        var tags []string
        for _, match := range matches {
            if len(match) > 1 {
                tags = append(tags, strings.TrimSpace(match[1]))
            }
        }
        return tags
    }

    // 3. Разделяем по запятым
    parts := strings.Split(s, ",")
    var tags []string
    for _, part := range parts {
        tag := strings.TrimSpace(part)
        if tag != "" {
            tags = append(tags, tag)
        }
    }

    return tags
}

func processUsersWithCursorPagination(news NewsMessage) {
	limit := 100
	lastID := int64(0)

	// Создаем пул горутин
	maxGoroutines := 50
	semaphore := make(chan struct{}, maxGoroutines)
	var wg sync.WaitGroup

	for {
		users, err := getUsersBatch(lastID, limit)
		if err != nil {
			log.Printf("Error getting users batch: %v", err)
			return
		}

		if len(users) == 0 {
			break // Все пользователи обработаны
		}

		// Обрабатываем каждого пользователя с ограничением количества одновременных горутин
		for _, user := range users {
			wg.Add(1)
			semaphore <- struct{}{} // Acquire semaphore

			go func(u User) {
				defer wg.Done()
				defer func() { <-semaphore }() // Release semaphore

				processUser(u, news)
			}(user)
		}

		// Обновляем lastID для следующей итерации
		lastID = users[len(users)-1].TelegramID
	}

	wg.Wait() // Ждем завершения всех горутин
}

func getUsersBatch(lastID int64, limit int) ([]User, error) {
	query := `SELECT telegram_id, first_name, username, is_premium, is_admin, 
		LLM_model, alert_config_general, alert_config_specific, language 
		FROM users WHERE telegram_id > ? ORDER BY telegram_id LIMIT ?`

	rows, err := db.Query(query, lastID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []User
	for rows.Next() {
		var user User
		var generalJSON, specificJSON []byte

		err := rows.Scan(
			&user.TelegramID,
			&user.FirstName,
			&user.Username,
			&user.IsPremium,
			&user.IsAdmin,
			&user.LLMModel,
			&generalJSON,
			&specificJSON,
			&user.Language,
		)
		if err != nil {
			return nil, err
		}

		// Парсим JSON один раз здесь
		if err := json.Unmarshal(generalJSON, &user.AlertConfigGeneral); err != nil {
			log.Printf("Error parsing general tags for user %d: %v", user.TelegramID, err)
			user.AlertConfigGeneral = []string{}
		}

		if err := json.Unmarshal(specificJSON, &user.AlertConfigSpecific); err != nil {
			log.Printf("Error parsing specific tags for user %d: %v", user.TelegramID, err)
			user.AlertConfigSpecific = []string{}
		}

		users = append(users, user)
	}

	return users, nil
}

func processUser(user User, news NewsMessage) {
	// Теперь JSON уже распарсен в структуре User
	// Проверяем условия отправки уведомления
	if shouldSendNotification(news.Tags, user.AlertConfigGeneral, user.AlertConfigSpecific) {
		sendAlert(user.TelegramID, news.Text)
	}
}

func shouldSendNotification(newsTags, generalTags, specificTags []string) bool {
	totalTags := len(newsTags)
	if totalTags == 0 {
		return false
	}

	// Проверяем общие теги (70% совпадение)
	generalMatch := calculateMatchPercent(newsTags, generalTags)
	if generalMatch >= 70 {
		return true
	}

	// Проверяем специфические теги (20% совпадение)
	specificMatch := calculateMatchPercent(newsTags, specificTags)
	if specificMatch >= 20 {
		return true
	}

	return false
}

func calculateMatchPercent(newsTags, userTags []string) float64 {
	if len(newsTags) == 0 {
		return 0
	}

	// Создаем множество тегов новости для быстрого поиска
	newsTagSet := make(map[string]struct{}, len(newsTags))
	for _, tag := range newsTags {
		newsTagSet[strings.ToLower(tag)] = struct{}{}
	}

	matchCount := 0
	for _, userTag := range userTags {
		if _, exists := newsTagSet[strings.ToLower(userTag)]; exists {
			matchCount++
		}
	}

	return float64(matchCount) / float64(len(newsTags)) * 100
}

func sendAlert(userID int64, text string) {
	alert := AlertMessage{
		UserID: userID,
		Text:   text,
	}

	// Отправляем в стрим alerts
	values := map[string]interface{}{
		"user_id": alert.UserID,
		"text":    alert.Text,
	}

	_, err := rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: "alerts",
		Values: values,
	}).Result()

	if err != nil {
		log.Printf("Error sending alert for user %d: %v", userID, err)
	} else {
		log.Printf("Alert sent for user %d", userID)
	}
}
