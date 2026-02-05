var start = 0
const RANDOM_QUOTE_API_URL = 'http://api.quotable.io/random'
const content = document.querySelector('#type_content')
const typeInput = document.querySelector('#type')
const timer = document.querySelector('#timer')
const speed = document.querySelector('#speed')
const car = document.querySelector('#car' + window.user.id)
let arrayQuote
let startTime
let countDown
let speedCount
let carUpdate
let summary
let startType = false

typeInput.onpaste = e => e.preventDefault();

function getRandomQuote() {
  return fetch(RANDOM_QUOTE_API_URL)
    .then(response => response.json())
    .then(data => data.content)
}

function renderNewQuote() {
  const quote = window.data
  content.innerHTML = ''
  quote.split('').forEach(char => {
    const characterSpan = document.createElement('span')
    const charText = document.createTextNode(char)
    characterSpan.appendChild(charText)
    content.appendChild(characterSpan)
  })
  typeInput.value = null
  arrayQuote = content.querySelectorAll('span')
  summary = arrayQuote.length
}

typeInput.addEventListener('input', function() {
  if (!startType) {
    startTimer()
    setSpeed()
    carAnimate()
    startType = true
  }
  typeInput.classList.remove('incorrect')
  const arrayValue = typeInput.value.split('')
  var i = start
  while (i < arrayQuote.length && arrayQuote[i] != ' ') {
    arrayQuote[i].classList.remove('correct')
    arrayQuote[i].classList.remove('incorrect')
    i += 1
  }
  const correct = true
  arrayValue.forEach((character, index) => {
    if (correct) {
      if (start + index == arrayQuote.length && character == ' ') {
        clearInterval(countDown)
        clearInterval(speedCount)
        clearInterval(carUpdate)
        car.style.left = '98%'
        start = start + index
        speed.innerText = calSpeed()
        content.innerHTML = 'Congratulation'
        typeInput.value = null
        typeInput.disabled = 'disabled'
      } else {
        const answer = arrayQuote[index + start].innerText
        if (character === answer) {
          arrayQuote[index + start].classList.add('correct')
          if (answer == ' ') {
            typeInput.value = null
            start = index + start + 1
          }
        } else {
          arrayQuote[index + start].classList.add('incorrect')
          typeInput.classList.add('incorrect')
          correct = false
        }
      }
    }
  })
})

function carAnimate() {
  carUpdate = setInterval(() => {
    car.style.left = (start * 100 / summary) + '%'
  }, 1000)
}

function calSpeed() {
  return Math.floor(start * 60 * 1000 / (new Date() - startTime))
}

function setSpeed() {
  speedCount = setInterval(() => {
    speed.innerText = calSpeed()
  }, 5000)
}

function startTimer() {
  timer.innerText = 0
  startTime = new Date()
  countDown = setInterval(() => {
    timer.innerText = getTimerTime()
  }, 1000)
}

function getTimerTime() {
  return Math.floor((new Date() - startTime) / 1000)
}